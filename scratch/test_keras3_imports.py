try:
    import keras
    print(f"Keras version: {keras.__version__}")
    from keras import Model
    print("SUCCESS: keras.Model imported")
    from keras.applications.vgg16 import VGG16, preprocess_input
    print("SUCCESS: keras.applications.vgg16 imported")
    from keras.utils import load_img, img_to_array
    print("SUCCESS: keras.utils.load_img/img_to_array imported")
except ImportError as e:
    print(f"IMPORT ERROR: {e}")
except Exception as e:
    print(f"ERROR: {e}")
