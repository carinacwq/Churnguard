from flask import Flask, request, send_from_directory, jsonify
import pandas as pd
from pymongo import MongoClient, ReturnDocument
import atexit
from bson import ObjectId
import bcrypt
import pickle
import joblib
from dotenv import load_dotenv
import os
from h2ogpte import H2OGPTE
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
import numpy as np
import bcrypt

app = Flask(__name__, static_folder='frontend')

# MongoDB client setup
client = MongoClient("mongodb://mongo:27017/")
db = client["AteamBank"]
collection = db["customer_details"]
users = db["users"]

# LLM setup (H2O.AI)
load_dotenv()
api_key = os.getenv("API_KEY")

llm_client = H2OGPTE(
    address='https://h2ogpte.genai.h2o.ai',
    api_key=api_key
)
# for gxs products
gxs_collection_id = os.getenv("GXS_COLLECTION_ID")
gxs_chat_id = os.getenv("GXS_CHAT_ID")

# for general bank customer retention strategies 
playbook_collection_id = os.getenv("CRM_PLAYBOOK_COLLECTION_ID")
playbook_chat_id = os.getenv("CRM_PLAYBOOK_CHAT_ID")

# the chat we use to recommend customer retention based on gxs products (combination of both the other 2 collections)
recommendation_collection_id = os.getenv("RECOMMENDATION_COLLECTION_ID")
recommendation_chat_id = os.getenv('RECOMMENDATION_CHAT_ID')

# for prompt engineering
pre_prompt = 'Imagine you are on the data science team of GXS, taking note that churn being 0 means no churn and churn being 1 means they have or are predicted to churn. If the client has a low balance and has churn = 1, it is likely that they have churned and withdrawn all their accounts, do take note of this when recommending. Take note that if churn is 0, we should recommend how to retain the customer by building brand loyalty for example. This is your clients information: '
post_prompt = ' What would you recommend to the customer relations team to retain the customer in general, give 2 suggestions based on the products available (huge emphasis on this) and the customer profile. If there are any recommendations, make sure to suggest a GXS programme or product that can be recommended.'


@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/register', methods=['POST'])
def register():
    username = request.json.get('username')
    password = request.json.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Missing username or password'}), 400

    if users.find_one({'username': username}):
        return jsonify({'error': 'Username already exists'}), 409

    hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    users.insert_one({'username': username, 'password': hashed_pw})

    return jsonify({'message': 'User created successfully'}), 201

@app.route('/login', methods=['POST'])
def login():
    username = request.json.get('username')
    password = request.json.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Missing username or password'}), 400

    # Find user in database
    user = users.find_one({'username': username})

    if user and bcrypt.checkpw(password.encode('utf-8'), user['password']):
        return jsonify({'message': 'Login successful'}), 200
    else:
        return jsonify({'error': 'Invalid username or password'}), 401

# initialize the database
@app.route('/upload-all', methods=['POST'])
def upload_file():
    file = request.files['file']
    print(file)
    if file.filename == '':
        return "No selected file", 400
    if file and file.filename.endswith('.xlsx'):
        df = pd.read_excel(file)
        # Convert DataFrame to dict and insert into MongoDB
        records = df.to_dict(orient='records')
        collection.insert_many(records)
        return "File successfully uploaded and data inserted into MongoDB", 200
    else:
        return "Invalid file format. Only .xlsx files are allowed.", 400

# Get all data from MongoDB
@app.route('/data', methods=['GET'])
def get_data():
    records = collection.find({})
    data_list = list(records)
    for record in data_list:
        record['_id'] = str(record['_id'])
    return jsonify(data_list)

# Test if api is working 
@app.route('/test', methods=['GET'])
def test():
    return "Good", 200

@app.route('/delete-all', methods=['DELETE'])
def delete_database():
    # Iterate through all collections in the database and drop each
    collection_names = db.list_collection_names()
    for collection_name in collection_names:
        db[collection_name].drop()
    return "Database successfully deleted", 200

# Deleting record
@app.route('/delete-client', methods=['DELETE'])
def delete_row():
    if not request.json or 'id' not in request.json:
        return jsonify({'error': 'Missing id in request'}), 400
    # Extract the ID from the request and convert it to ObjectId
    try:
        id_to_delete = (request.json['id'])
    except:
        return jsonify({'error': 'Invalid ID format'}), 400
    # Perform the deletion
    result = collection.delete_one({'CustomerID': id_to_delete})
    # Check if a document was deleted
    if result.deleted_count > 0:
        return jsonify({'message': 'Row successfully deleted'}), 200
    else:
        return jsonify({'error': 'Row not found'}), 404

@app.route('/create-client', methods=['POST'])
def add_client():
    try:
        client_data = request.json

        # Check if the CustomerID already exists in the database
        if 'CustomerID' in client_data:
            existing_client = collection.find_one({"CustomerID": client_data['CustomerID']})
            if existing_client:
                return jsonify({'error': 'A client with the given CustomerID already exists'}), 400

        # If _id is specified for some reason, ensure it's an ObjectId
        if client_data.get('_id'):
            client_data['_id'] = ObjectId(client_data['_id'])

        result = collection.insert_one(client_data)
        return jsonify({'message': 'Client added successfully', 'id': str(result.inserted_id)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/update-client/<CustomerID>', methods=['POST'])
def update_client(CustomerID):
    try:
        update_data = request.json
        # Ensure _id and customer_id retains the original values
        update_data.pop('_id', None) 
        update_data.pop('CustomerID', None)

        # Find one client matching the customer_id and update it
        result = collection.find_one_and_update(
            {"CustomerID": int(CustomerID)}, 
            {"$set": update_data},
            return_document=ReturnDocument.AFTER
        )
        if result:
            return jsonify({'message': 'Client updated successfully', 'id': str(result['_id'])}), 200
        else:
            return jsonify({'message': 'Client not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/read-client/<CustomerID>', methods=['GET'])
def read_client(CustomerID):
    try:
        CustomerID = int(CustomerID)
    except ValueError:
        return jsonify({'error': 'CustomerID must be an integer'}), 400

    # Find the client by CustomerID
    client_data = collection.find_one({"CustomerID": CustomerID}, {"_id": 0}) 

    if client_data:
        return jsonify(client_data), 200
    else:
        return jsonify({'message': 'Client not found'}), 404
    

@app.route('/login', methods=['POST'])
def login_user():
    try:
        user_data = request.json
        if not user_data or 'username' not in user_data or 'password' not in user_data:
            return jsonify({'error': 'Missing username or password'}), 400

        username = user_data['username']
        password = user_data['password'].encode('utf-8')

        # Retrieve user from database
        user = collection.find_one({"username": username})
        if not user:
            return jsonify({'error': 'Invalid username or password'}), 401
        
        # Verify the password
        if bcrypt.checkpw(password, user['password'].encode('utf-8')):
            return jsonify({'message': 'Login successful'}), 200
        else:
            return jsonify({'error': 'Invalid username or password'}), 401

    except Exception as e:
        return jsonify({'error': 'Server error'}), 500

# routes for AI recommendation using H2O's LLM
@app.route('/suggest-client/<CustomerID>', methods=['GET'])
def suggest_product(CustomerID):
    try:
        CustomerID = int(CustomerID)
    except ValueError:
        return jsonify({'error': 'customer_id must be an integer'}), 400
    
    client_data = collection.find_one({"CustomerID": CustomerID}, {"_id": 0}) 

    if client_data:
        try:
            with llm_client.connect(gxs_chat_id) as session:
                reply = session.query(
                    pre_prompt + str(client_data) + post_prompt,
                    timeout=120
                )
        except:
            return jsonify({'message': 'Session Timeout: Invalid Chat ID'}), 500
        if reply:
            return jsonify(reply.content), 200
        else:
            return jsonify({'message': 'H2O.AI not found'}), 404
    else:
        return jsonify({'message': 'Client not found'}), 404

# Load the model and preprocessor
model = joblib.load('Gradient Boosting_best_model.pkl')
preprocessor = joblib.load('preprocessor.pkl')

@app.route('/predict', methods=['POST'])
def predict():
    try:
        data = request.get_json(force=True)
        required_features = [
            'Age', 'EmploymentStatus', 'HousingStatus', 'ActiveMember', 'Country',
            'EstimatedSalary', 'Balance', 'Gender', 'ProductsNumber', 'DebitCard',
            'SavingsAccount', 'FlexiLoan', 'Tenure', 'DaysSinceLastTransaction',
            'CustomerEngagementScore', 'TechSupportTicketCount', 'NumberOfAppCrashes',
            'NavigationDifficulty', 'UserFrustration', 'CustomerSatisfactionSurvey',
            'CustomerServiceCalls', 'NPS'
        ]

        # Check for the existence of all required features
        if not all(feature in data for feature in required_features):
            return jsonify({'error': 'Missing one or more of the required features'}), 400

        # Create DataFrame
        df = pd.DataFrame([data])
        
        # Check that all columns are present after creating the DataFrame
        if not all(column in df.columns for column in required_features):
            return jsonify({'error': 'Missing one or more of the required features in DataFrame'}), 400

        # Apply preprocessing
        preprocessed_features = preprocessor.transform(df)
        
        # Predict using the preprocessed features
        prediction = model.predict(preprocessed_features)[0]
        return jsonify({'prediction': prediction})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/batch-predict-update', methods=['GET'])
def batch_predict_update():
    try:
        # Setup MongoDB client and select collection
        client = MongoClient('mongodb_connection_string')
        db = client['database_name']
        collection = db['collection_name']

        # Fetch data from MongoDB
        records = collection.find({})
        data_list = list(records)
        
        for record in data_list:
            record['_id'] = str(record['_id'])  # Convert ObjectId to string for JSON compatibility
            
        required_features = [
            'Age', 'EmploymentStatus', 'HousingStatus', 'ActiveMember', 'Country',
            'EstimatedSalary', 'Balance', 'Gender', 'ProductsNumber', 'DebitCard',
            'SavingsAccount', 'FlexiLoan', 'Tenure', 'DaysSinceLastTransaction',
            'CustomerEngagementScore', 'TechSupportTicketCount', 'NumberOfAppCrashes',
            'NavigationDifficulty', 'UserFrustration', 'CustomerSatisfactionSurvey',
            'CustomerServiceCalls', 'NPS'
        ]
        # Convert list of dictionaries to DataFrame
        df = pd.DataFrame(data_list)
        
        # Check that all columns are present
        if not all(column in df.columns for column in required_features):
            return jsonify({'error': 'Missing one or more of the required features in data'}), 400

        # Apply preprocessing
        preprocessed_features = preprocessor.transform(df[required_features])
        
        # Predict using the preprocessed features
        predictions = model.predict(preprocessed_features)
        
        # Update MongoDB with the new 'Persona' predictions
        for record, prediction in zip(data_list, predictions):
            collection.update_one({'_id': ObjectId(record['_id'])}, {'$set': {'Persona': prediction}})

        return jsonify({'message': 'Batch prediction and update completed successfully'}), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# for inidividual testing
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)