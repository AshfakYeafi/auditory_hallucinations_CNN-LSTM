# 25/4/2017
# This piece of code will run frames through vgg-19
# 'video_dset' = (112392,224,224,3)
# 'audio_dset' = (112392,18)

from extract_image_features.video_utils import *
import numpy as np
from extract_image_features.keras_pretrained_models.imagenet_utils import preprocess_input
from keras.models import Model
from extract_image_features.keras_pretrained_models.vgg19 import VGG19

### SET TO TRUE IF USING TITANX LINUX MACHINE
USE_TITANX = True

### Define video processing dimensions
frame_h = 224  # (60,60) maybe too small
frame_w = frame_h


### DEFINE OUTPUT DIRECTORY ###
if USE_TITANX:
    data_extern_dest = '/home/zanoi/ZANOI/auditory_hallucinations_data/'
else:  # Working on MacBook Pro
    data_extern_dest = '/Volumes/SAMSUNG_SSD_256GB/ADV_CV/data/'

data_file_name = data_extern_dest + 'TopAngleFC1_dataX_dataY.h5'

### LOADING VIDEOS ###
print ("--- Loading video and audio filenames...")
if USE_TITANX:
    video_dir = '/home/zanoi/ZANOI/auditory_hallucinations_videos'
else: # Working on MacBook Pro
    video_dir = "/Volumes/SAMSUNG_SSD_256GB/ADV_CV/4-24_VIDAUD/EXPORTS"

video_files = [os.path.join(video_dir, file_i)
         for file_i in os.listdir(video_dir)
         if file_i.endswith('.mp4')]

num_videos = len(video_files)
print("num_videos: ", num_videos)

### LOADING AUDIO ###
audio_feature_dir = "../audio_vectors"

audio_f_files = [os.path.join(audio_feature_dir, file_i)
                for file_i in os.listdir(audio_feature_dir)
                if file_i.endswith('.mat')]

num_audio_f = len(audio_f_files)
print("num_audio_f: ", num_audio_f)

### MAIN FUNCTION LOOP FOR PROCESSING TRAINING SET ###
for i in range(num_audio_f):  # Loop over all audio files
    audio_prefix, audio_vector_length, audio_features = returnAudioVectors(i, audio_f_files)
    print ("--------------------{ " + str(audio_prefix) + " }-----------------------")
    # Find all the linked videos for the given audio vector
    linked_video_f = findMatchingVideos(audio_prefix, video_files)
    print(audio_f_files[i])
    print(linked_video_f)

    for j, video_filename in enumerate(linked_video_f):

        # Process the videos linked to a particular audio vector
        ######## PROCESS VIDEO TO BLACK AND WHITE
        print("--- Processing video to greyscale...")

        output_dimensions = (frame_h,frame_w)
        processed_video = processOneVideo(audio_vector_length, video_filename, output_dimensions=output_dimensions, normalize=False)
        print("processed_video.shape:", processed_video.shape)

        ######### CONCATENATE INTO SPACETIME IMAGE
        print ("--- Concatenating into Spacetime image...")
        window = 3
        space_time_images = createSpaceTimeImagesforOneVideo(processed_video,window) # (8377, 224, 224, 3)
        print ("space_time_image.shape:", space_time_images.shape)
        (num_frames, frame_h, frame_w, channels) = space_time_images.shape

        ########## RUN THE SPACETIME IMAGES THROUGH VGG19
        print("--- Running through VGG19 FC1 layer...")
        # Build the model
        base_model = VGG19(weights='imagenet')
        model = Model(input=base_model.input,
                      output=base_model.get_layer('fc1').output)  # Only take the FC2 layer output

        # Preallocate matrix output
        CNN_FC_output = np.zeros((num_frames, 1, 4096))  # (1,8377,1,4096) -> FC2 outputs dimensions (1,4096)

        for frame_num in tqdm(range(num_frames)):
            img = space_time_images[frame_num]
            x = np.expand_dims(img, axis=0)
            x = preprocess_input(x)
            fc1_features = model.predict(x)  # Predict the FC2 features from VGG19, output shape is (1,4096)

            CNN_FC_output[frame_num] = fc1_features  # Save the FC2 features to a matrix
        print("CNN_FC_output.shape:", CNN_FC_output.shape)  # (8377,1,4096)

        ########### CREATE FINAL DATASET, concatenate FC output with audio vectors
        # To avoid memory problems, we incrementally add to h5py file. A single video is processed and dumped to the h5py
        if i == 0 and j == 0:
            # If this is the first video file, you need to create the first entry matrix
            with h5py.File(data_file_name, 'w') as f:
                # Create the dataset in the h5py file
                video_dset = f.create_dataset("dataX_train", CNN_FC_output.shape, maxshape=(None, 1, 4096))  # maxshape = (None, 224,224,3)

                # Normalization of the audio_vectors occurs in this function -> Hanoi forgot to normalize in MATLAB!!!!
                final_audio_vector = createAudioVectorDatasetForOneVid(audio_features,space_time_images.shape)  # (8377, 18)
                print("final_audio_vector.shape:", final_audio_vector.shape)
                audio_dset = f.create_dataset("dataY_train", final_audio_vector.shape, maxshape=(None, 18))

                print("Writing data to file...")
                video_dset[:] = CNN_FC_output
                audio_dset[:] = final_audio_vector

                print("video_dset.shape:", video_dset.shape)
                print("audio_dset.shape:", audio_dset.shape)
        else:
            with h5py.File(data_file_name, 'a') as hf:

                # Normalization of the audio_vectors occurs in this function -> Hanoi forgot to normalize in MATLAB!!!!
                final_audio_vector = createAudioVectorDatasetForOneVid(audio_features,
                                                                       space_time_images.shape)  # (8377, 18)
                print("final_audio_vector.shape:", final_audio_vector.shape)

                print("Writing data to file...")
                video_dset = hf['dataX_train']
                video_dset.resize(video_dset.len() + num_frames, axis=0)
                video_dset[-num_frames:] = CNN_FC_output
                audio_dset = hf['dataY_train']
                audio_dset.resize(audio_dset.len() + num_frames, axis=0)
                audio_dset[-num_frames:] = final_audio_vector

                print("video_dset.shape:", video_dset.shape)
                print("audio_dset.shape:", audio_dset.shape)

        print ("Current video complete!")

####### PROCESSING THE TEST SET
# There is only one video for test set
if USE_TITANX:
    test_video_filename = '/home/zanoi/ZANOI/auditory_hallucinations_videos/TEST_SET/seq7TEST_angle1.mp4'
else:  # Working on MacBook Pro
    test_video_filename = '/Volumes/SAMSUNG_SSD_256GB/ADV_CV/4-24_VIDAUD/EXPORTS/TEST_SET/seq7TEST_angle1.mp4'

test_audio_vector_filename = '../audio_vectors/TEST_SET/seq7TEST_audio_vectors.mat'

print ("--------------------{ PROCESSING TEST SET }-----------------------")
mat_contents = sio.loadmat(test_audio_vector_filename)  # 18 x n-2
audio_features = mat_contents['audio_vectors']
audio_vector_length = audio_features.shape[1]

print("--- Processing video to greyscale...")
output_dimensions = (frame_h,frame_w)
processed_video = processOneVideo(audio_vector_length, test_video_filename, output_dimensions=output_dimensions, normalize=False)
print("processed_video.shape:", processed_video.shape)

######### CONCATENATE INTO SPACETIME IMAGE
print ("--- Concatenating into Spacetime image...")
window = 3
space_time_images = createSpaceTimeImagesforOneVideo(processed_video,window) # (8377, 224, 224, 3)
print ("space_time_image.shape:", space_time_images.shape)
(num_frames, frame_h, frame_w, channels) = space_time_images.shape

########## RUN THE SPACETIME IMAGES THROUGH VGG19
print("--- Running through VGG19 FC2 layer...")
# Build the model
base_model = VGG19(weights='imagenet')
model = Model(input=base_model.input,
              output=base_model.get_layer('fc1').output)  # Only take the FC2 layer output

# Preallocate matrix output
CNN_FC_output = np.zeros((num_frames, 1, 4096))  # (1,8377,1,4096) -> FC2 outputs dimensions (1,4096)

for frame_num in tqdm(range(num_frames)):
    img = space_time_images[frame_num]
    x = np.expand_dims(img, axis=0)
    x = preprocess_input(x)
    fc1_features = model.predict(x)  # Predict the FC2 features from VGG19, output shape is (1,4096)

    CNN_FC_output[frame_num] = fc1_features  # Save the FC2 features to a matrix
print("CNN_FC_output.shape:", CNN_FC_output.shape)  # (1,8377,1,4096)

# Need to create a new dataset in the original h5py file for test set that is separate from training set
with h5py.File(data_file_name, 'a') as f:
    video_dset = f.create_dataset("dataX_test", CNN_FC_output.shape,
                                  maxshape=(None, 1, 4096))  # maxshape = (None, 224,224,3)

    # Normalization of the audio_vectors occurs in this function -> Hanoi forgot to normalize in MATLAB!!!!
    final_audio_vector = createAudioVectorDatasetForOneVid(audio_features, space_time_images.shape)  # (8377, 18)
    print("final_audio_vector.shape:", final_audio_vector.shape)
    audio_dset = f.create_dataset("dataY_test", final_audio_vector.shape, maxshape=(None, 18))

    print("Writing data to file...")
    video_dset[:] = CNN_FC_output
    audio_dset[:] = final_audio_vector

    print("video_dset.shape:", video_dset.shape)
    print("audio_dset.shape:", audio_dset.shape)

print ("Current video complete!")

print ("--- {EVERYTHING COMPLETE HOMIEEEEEEEEE} ---")