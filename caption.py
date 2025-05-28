import openai
import os#处理环境变量
import io#处理字节流数据
import base64
from PIL import Image
import json
def encode_image(image):
    image = image.resize((256, 256))
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')


client = openai.OpenAI(
# 若没有配置环境变量，请用百炼API Key将下行替换为：api_key="sk-xxx",
api_key="sk-74f4ad2a3c1c4d3d80665aa0403a0892", 
base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",)

image_path=r"C:\Users\26217\Pictures\Camera Roll\panda.jpg"
file_name = os.path.basename(image_path)
image = Image.open(image_path)
base64_image = encode_image(image)
try:#遇到异常继续执行
    completion = client.chat.completions.create(
        model="qwen-vl-plus", # 模型列表：https://help.aliyun.com/zh/model-studio/getting-started/models
        messages=[
                    {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Please output a detailed caption of the image."
                        },
                        {
                        "type": "image_url",
                        "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                        }
                            ]
                        }
            ]
        )
    caption=completion.choices[0].message.content#打印图片描述
    print(caption)#打印图片描述

except Exception as e:
    print("Some other request errors")