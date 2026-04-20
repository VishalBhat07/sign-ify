import pickle
import numpy as np
try:
    from skl2onnx import convert_sklearn
    from skl2onnx.common.data_types import FloatTensorType
except ImportError:
    print("skl2onnx not installed")
    exit(1)

def convert():
    print("Loading model.p...")
    with open('model.p', 'rb') as f:
        model_dict = pickle.load(f)
    model = model_dict['model']
    
    n_features = getattr(model, 'n_features_in_', 42)
    print(f"Detected {n_features} features in the RandomForestClassifier.")
    
    # Define input type
    initial_type = [('float_input', FloatTensorType([None, n_features]))]
    
    # Try converting
    print("Converting to ONNX...")
    onx = convert_sklearn(model, initial_types=initial_type)
    
    with open('model.onnx', 'wb') as f:
        f.write(onx.SerializeToString())
    print("Success! Created model.onnx")

if __name__ == '__main__':
    convert()
