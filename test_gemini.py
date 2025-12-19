# import google.generativeai as genai

# genai.configure(api_key='AIzaSyBMxFselQ9KWr9WV8KsngdkhKf0tCOxVp4')

# print("Available models:")
# for model in genai.list_models():
#     if 'generateContent' in model.supported_generation_methods:
#         print(f"- {model.name}")

import google.generativeai as genai

genai.configure(api_key='AIzaSyBMxFselQ9KWr9WV8KsngdkhKf0tCOxVp4')

# Use newest free model
model = genai.GenerativeModel('gemini-2.5-flash')
response = model.generate_content('Generate SQL: show all users')
print(response.text)