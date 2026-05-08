def lambda_handler(event, context):
    print("CanopyID Lambda")
    return {
        "statusCode": 200,
        "body": "Hello"
    }