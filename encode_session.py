import base64

with open('my_session.session', 'rb') as f:
    data = f.read()

encoded = base64.b64encode(data).decode('utf-8')
print(encoded)
