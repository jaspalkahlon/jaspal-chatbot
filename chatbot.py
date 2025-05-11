from openai import OpenAI
import gradio as gr
import docx
import os

# Set up Open AI API key from environment variable
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Read Word file
try:
    doc = docx.Document("jaspalpersonal.docx")
    word_data = "\n".join([para.text for para in doc.paragraphs if para.text])
except Exception as e:
    word_data = f"Error reading Word: {str(e)}"

# Custom instructions
custom_instructions = "You are jaspal's bot. you are here to answer queries from visitors to Jaspal's website. Your tone will be friendly, answer in English (preferred), or hindi or punjabi as the user prompts in the language. you will use the vocabulary of a 18 year old non-native english speaker. Tone - friendly but to the point with a hint of 'mentoring'. Do not talk about my personal life other than in public domain. Use the following Word document data to inform your answers:\n\nWord Data:\n{word_data}".format(word_data=word_data)

# Function to handle chat, generate response, and clear input
def chat(user_input, history):
    # Initialize chat history for Open AI if it's the first message (history is None or empty)
    if history is None or len(history) == 0:
        chat_history = [
            {"role": "system", "content": custom_instructions}
        ]
        ui_messages = []
    else:
        # Reconstruct chat_history from UI history for Open AI
        chat_history = [{"role": "system", "content": custom_instructions}]
        for user_msg, assistant_msg in history:
            chat_history.append({"role": "user", "content": user_msg})
            chat_history.append({"role": "assistant", "content": assistant_msg})
        ui_messages = history

    # Add user input to chat history
    chat_history.append({"role": "user", "content": user_input})
    
    # Send history to Open AI
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=chat_history
    )
    
    # Get AI response and add to history
    ai_response = response.choices[0].message.content
    
    # Add to UI messages (list of [user, assistant] pairs)
    ui_messages.append([user_input, ai_response])
    
    # Return updated chat and clear the textbox
    return ui_messages, ""

# Custom CSS for modern chatbot styling
css = """
.chatbot .message.user { 
    background-color: #007BFF; 
    color: #FFFFFF; 
    margin-left: 30%; 
    margin-right: 10px; 
    margin-bottom: 15px;
    border-radius: 15px; 
    padding: 12px 16px; 
    text-align: right; 
    display: inline-block;
    max-width: 70%;
    box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 16px;
    line-height: 1.4;
    white-space: pre-wrap;
}
.chatbot .message.assistant { 
    background-color: #F1F3F5; 
    color: #000000; 
    margin-right: 30%; 
    margin-left: 10px; 
    margin-bottom: 15px;
    border-radius: 15px; 
    padding: 12px 16px; 
    text-align: left; 
    display: inline-block;
    max-width: 70%;
    box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 16px;
    line-height: 1.4;
    white-space: pre-wrap;
}
.chatbot { 
    background-color: #FFFFFF; 
    border-radius: 15px; 
    height: 400px; 
    overflow-y: auto; 
    box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
    padding: 15px;
    margin-bottom: 15px;
}
.chatbot-container { 
    background-color: #F9FAFB; 
    padding: 20px; 
    border-radius: 15px; 
}
.gr-textbox input { 
    background-color: #FFFFFF !important; 
    border: 1px solid #E2E8F0 !important; 
    border-radius: 10px !important; 
    padding: 10px 15px !important; 
    box-shadow: 0 2px 5px rgba(0, 0, 0, 0.05) !important; 
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important; 
    font-size: 16px !important; 
    color: #333333 !important; 
}
.gr-textbox input:focus { 
    outline: none !important; 
    border-color: #007BFF !important; 
    box-shadow: 0 0 0 3px rgba(0, 123, 255, 0.1) !important; 
}
.gr-textbox label { 
    color: #333333 !important; 
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important; 
    font-size: 14px !important; 
    margin-bottom: 5px !important; 
}
h1 { 
    color: #1F2937; 
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
    font-size: 24px; 
    font-weight: 600; 
    text-align: center; 
    margin-bottom: 20px; 
}
"""

# Create Gradio interface with Chatbot component
with gr.Blocks(css=css) as interface:
    gr.Markdown("# Jaspal's Chatbot")
    chatbot = gr.Chatbot(label="Chat with Jaspal's Bot", elem_classes="chatbot")
    user_input = gr.Textbox(placeholder="Type your message here...", label="Message")
    user_input.submit(chat, inputs=[user_input, chatbot], outputs=[chatbot, user_input])

# Launch the chatbot, binding to 0.0.0.0 and the PORT environment variable
port = int(os.getenv("PORT", 7860))  # Use Render's PORT or default to 7860 locally
interface.launch(server_name="0.0.0.0", server_port=port)