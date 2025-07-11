import base64
import json
from openai import OpenAI



def text_to_text(api_key:str, message:list, model:str):
    client = OpenAI(api_key=api_key)
    stream = client.responses.create(
        model=model,
        input=message,
        stream=True
    )
    final_response = None
    for event in stream:
        if event.type == "response.output_text.delta":
            pass
        elif event.type == "response.completed":
            final_response = event.response
        elif event.type == "error":
            pass


    input_tokens = final_response.usage.input_tokens
    output_tokens = final_response.usage.output_tokens
    ai_text = final_response.output[0].content[0].text
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "ai_text": ai_text
    }


