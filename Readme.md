<!-- cloudinary.api.delete_resources_by_prefix(f"documents/{user_id}/", resource_type="raw") -->

## local run

```
python -m venv venv
venv\Scripts\activate //  (for window)
pip install -r requirements.txt
uvicorn main:app --reload
```

## env

```
MONGO_PASSWORD=
MONGO_USERNAME=
MONGO_URI=
MONGO_DB_NAME=
GEN_AI_API_KEY=

AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=
AWS_S3_BUCKET_NAME=
```
