from django.test import TestCase

# Create your tests here.

for item in range(4):
    try:
        print(item)
    except Exception as e:
        print(e)
    else:
        print('else try')