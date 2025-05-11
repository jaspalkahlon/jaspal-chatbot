from openai import OpenAI
import gradio as gr
import docx
import os

# Set up Open AI API key from environment variable
client = OpenAI(api_key=os.getenv("OPENAI_APsk-proj-szmRdlpC6YCaVpM-COgeKoIBU4F6ldza3zuM0U1gjIjexkbSnh0Ip-7wIC4d7IOdBlw37x5397T3BlbkFJ2prY3yysKP3qEiLHCEifI5d6SEUI143bjJgGRbdYdsaolCj1Wu318ty0sIBV2oBeB3o-6qq1kA"))

# Read Word file
try:
    doc = docx.Document("jaspalpersonal.docx")
    word_data = "\n".join([para.text for para in doc.paragraphs if para.text])
except Exception as e:
    word_data = f"Error reading Word: {str(e)}"

# Custom instructions
custom_instructions = "You are jaspal's bot. you are here to answer queries from visitors to Jaspal's website. Your tone will be friendly, answer in English (preferred), or hindi or punjabi as the user prompts in the language. you will use the vocabulary of a 18 year old non-native english speaker. Tone - friendly but to the point with a hint of 'mentoring'. Do not talk about my personal life other than in public domain. Use the following Word document data to inform your answers:\n\nWord Data:\n{word_data}".format(word_data=word_data)

# Store chat history for Open AI
chat_history = [
    {"role": "system", "content": custom_instructions}
]

# Store messages for Gradio Chatbot UI
ui_messages = []

# Function to handle chat, generate response, and clear input
def chat(user_input):
    # Add user input to chat history
    chat_history.append({"role": "user", "content": user_input})
    
    # Send history to Open AI
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=chat_history
    )
    
    # Get AI response and add to history
    ai_response = response.choices[0].message.content
    chat_history.append({"role": "assistant", "content": ai_response})
    
    # Add to UI messages (list of [user, assistant] pairs)
    ui_messages.append([user_input, ai_response])
    
    # Return updated chat and clear the textbox
    return ui_messages, ""

# Custom CSS for WhatsApp-like styling
css = """
.chatbot .message.user { 
    background-color: #DCF8C6; 
    color: #000000; 
    margin-left: 40%; 
    margin-right: 5px; 
    margin-bottom: 10px;
    border-radius: 10px; 
    padding: 8px; 
    text-align: right; 
    display: block;
    min-height: 20px;
    white-space: pre-wrap;
}
.chatbot .message.assistant { 
    background-color: #FFFFFF; 
    color: #000000; 
    margin-right: 40%; 
    margin-left: 5px; 
    margin-bottom: 10px;
    border-radius: 10px; 
    padding: 8px; 
    text-align: left; 
    display: block;
    min-height: 20px;
    white-space: pre-wrap;
}
.chatbot { 
    background-color: #ECE5DD; 
    border-radius: 10px; 
    height: 500px; 
    overflow-y: scroll; 
}
.chatbot-container { 
    background-color: #ECE5DD; 
    padding: 10px; 
}
"""

# Create Gradio interface with Chatbot component
with gr.Blocks(css=css) as interface:
    gr.Markdown("# Jaspal's Chatbot")
    chatbot = gr.Chatbot(label="Chat with Jaspal's Bot", elem_classes="chatbot")
    user_input = gr.Textbox(placeholder="Type your message here...", label="Message")
    user_input.submit(chat, inputs=user_input, outputs=[chatbot, user_input])

# Launch the chatbot, binding to 0.0.0.0 and the PORT environment variable
port = int(os.getenv("PORT", 7860))  # Use Render's PORT or default to 7860 locally
interface.launch(server_name="0.0.0.0", server_port=port)