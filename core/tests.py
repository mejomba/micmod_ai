from django.test import TestCase

# Create your tests here.

class F:
    d = 1
    def __init__(self):
        c = 2

if __name__ == '__main__':
    f1 = F()
    f1.d = 3
    f2 = F()
    print(f2.d)