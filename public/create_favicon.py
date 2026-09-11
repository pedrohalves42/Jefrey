from PIL import Image
img = Image.new('RGB', (64, 64), 'white')
img.save('favicon.ico')
print('Created favicon.ico')