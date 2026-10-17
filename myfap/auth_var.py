import base64

# encode sang Base64 để né search engine bot hoặc ai scrapper (méo bt có né dc ko)
_FEID_HOST_B64 = b'aHR0cHM6Ly9mZWlkLmZwdC5lZHUudm4='
_FAP_HOST_B64 = b'aHR0cHM6Ly9hcGkuZnB0LmVkdS52bi9mYXAvYXBpL015RkFQ'
_CLIENT_ID_B64 = b'ZmFwLW1vYmlsZS1mcm9udC1lbmQ='
_REDIRECT_URI_B64 = b'aW8uaWRlbnRpdHlzZXJ2ZXIuZGVtbzovb2F1dGhyZWRpcmVjdA=='
_SECRET_KEY_B64 = b'bjRBU3Nia2FXNmRkaElrRjBpcGlObXhJTW56aXgzbFJlNjJzMm1Ub2JLbmsyZW5BMmVvWlFNeWJGM2dlTGNONVV3MGxSM05YemJnZDltUUgwMHFzTndiQ0haVzBmT00wOHRBRmZjUzBBQXpQRnVjdGxKZU1WdXF4dUdOMmZOUlY='
_MAGIC_ID_B64 = b'VGxLaUEwMzQwcFk2SGtpbzRrYVRMRk12eEs3R0lPbHI2eHFWN21WQUk0YlJjaDdzZmpPT3g3Rm5JcFYxZHd2dmVIMGo1eHNSektsUkQ2c3FOT0F5MEc0OTJjbVFCNXhsSVFORmlYeVMyOHBYVlhUTjdFbXk3N3ZITmFzMmtMcEU='

FEID_HOST = base64.b64decode(_FEID_HOST_B64).decode()
FAP_HOST = base64.b64decode(_FAP_HOST_B64).decode()
CLIENT_ID = base64.b64decode(_CLIENT_ID_B64).decode()
REDIRECT_URI = base64.b64decode(_REDIRECT_URI_B64).decode()
SECRET_KEY = base64.b64decode(_SECRET_KEY_B64).decode()
MAGIC_ID = base64.b64decode(_MAGIC_ID_B64).decode()

# Hằng giao thức survey từ app; không phải credential của người dùng.
_SURVEY_SECRET_KEY_B64 = b'MmViOTc0OTI4MDMxZTcxYmYyNDFjZmNmY2NhMDM3NjJlZDJmMGZlZg=='
SURVEY_SECRET_KEY = base64.b64decode(_SURVEY_SECRET_KEY_B64).decode()

# Hằng giao thức v2 từ app; không phải credential của người dùng.
_FAP_PROXY_HOST_B64 = b'aHR0cHM6Ly9mYXAtcHJveHkuZnB0LmVkdS52bi9NeUZBUA=='
_V2_SECRET_KEY_B64 = b'MmViZjc2YmU2YTdmNTdkYWE4YjI5N2YzOTI2MzlkMjE4NjRjZTliMDY2ZTU0NmY0ZWEyMGJhNzgyMTE4MzcyMjhkZWU0NTJkMDAzOWViODMwYjdhY2QyN2YwY2MxNGYwY2YwYThjNzhlNDgzZDVlYzkzOGYzZjk4NGY0NTdjMzU='
_V2_BOOTSTRAP_TOKEN_B64 = b'NjljYjk4ZTE2ZWVmMGQyMWU1NTg2NWE0'

FAP_PROXY_HOST = base64.b64decode(_FAP_PROXY_HOST_B64).decode()
V2_SECRET_KEY = base64.b64decode(_V2_SECRET_KEY_B64).decode()
V2_BOOTSTRAP_TOKEN = base64.b64decode(_V2_BOOTSTRAP_TOKEN_B64).decode()
V2_CLIENT_CODE = "MyFAP"
