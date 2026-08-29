print('before import')
from pydantic_settings import BaseSettings
print('after import')
class Test(BaseSettings):
    test: str = 'default'
print('class defined')
t = Test()
print('instance created:', t.test)