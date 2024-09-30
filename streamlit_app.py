import streamlit as st
from openai import OpenAI
import pandas as pd
import os
import utils
import openpyxl

from langchain_community.chat_models import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain.prompts import PromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, ChatPromptTemplate
from langchain_core.prompts import MessagesPlaceholder
from langchain.chains import LLMChain, ConversationChain
from langchain_core.output_parsers import StrOutputParser
from langchain.memory import ConversationBufferMemory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain.schema import AIMessage, HumanMessage
from langchain_community.chat_message_histories import StreamlitChatMessageHistory

# Show title and description.
st.title("💬 Testing Chatbot")
st.write(
    "This is a chatbot that uses OpenAI's GPT-4o model to generate responses. "
)

# Get participant ID 
user_PID = st.text_input("What is your participant ID?")
# Example options for the dropdown
options = ['authoritative', 'talktative', 'informality', 'sentimentality', 'conciseness', 'conversational dominance']

# Create a dropdown selection box
target_style = st.selectbox('Choose a communication st:', options)

# Display the selected option
st.write(f'You selected: {target_style}')

# Retrieve api key from secrets
openai_api_key = st.secrets["OPENAI_API_KEY"]

if not openai_api_key:
    st.info("Please add your OpenAI API key to continue.", icon="🗝️")
else:

    # Create an OpenAI client.
    llm = ChatOpenAI(model="gpt-4o-mini", api_key=openai_api_key)

    # Load prompts
    file_path = 'therapyagent_system_prompt.txt'
    with open(file_path, 'r') as file:
        system_prompt_text = file.read()
    file_path = 'csm_system_prompt.txt'
    with open(file_path, 'r') as file:
        csm_prompt_text = file.read()

    # Therapy agent prompt 
    therapyagent_prompt_template = ChatPromptTemplate.from_messages([
        ("system", system_prompt_text),
        MessagesPlaceholder(variable_name="history"), # dynamic insertion of past conversation history
        ("human", "{input}"),
    ])

    # Communication style modifier prompt
    csm_prompt_template = PromptTemplate(
        variables=["communication_style", "chat_history", "unadapted_response"], template=csm_prompt_text
    )

    # set up streamlit history memory
    msgs = StreamlitChatMessageHistory(key="chat_history")

    # Create a session state variable to store the chat messages. This ensures that the
    # messages persist across reruns.
    if "messages" not in st.session_state:
        st.session_state.messages = [
            # Prewritten first turn
            {"role": "user", "content": "Hello."},
            {"role": "assistant", "content": "Hello there! How are you feeling today?"},
        ]

    # Display the existing chat messages via `st.chat_message`.
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Create a chat input field to allow the user to enter a message. This will display
    # automatically at the bottom of the page.
    if user_input := st.chat_input("Enter your input here."):
        
        # create a therapy chatbot llm chain
        therapyagent_chain = therapyagent_prompt_template | llm
        therapy_chain_with_history = RunnableWithMessageHistory(
            therapyagent_chain,
            lambda session_id: msgs,  # Always return the instance created earlier
            input_messages_key="input",
            # output_messages_key="content",
            history_messages_key="history",
        )

        # create a csm chain
        csmagent_chain = LLMChain(
            llm=llm,
            prompt=csm_prompt_template,
            verbose=False,
            output_parser=StrOutputParser()
        )


        # Store and display the current prompt.
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)


        config = {"configurable": {"session_id": "any"}}
        unada_response = therapy_chain_with_history.invoke({"input": user_input}, config)
        unada_bot_response = unada_response.content


        # input target style dictionary
        style_dict = pd.read_excel("style_dict.xlsx", header=0, sheet_name=0)
        selected_style_row = style_dict[style_dict['style']==target_style]
        definition = selected_style_row['definition']
        survey_item = selected_style_row['survey_item']
        ada_response = csmagent_chain.predict(communication_style=target_style,
                                            definition=definition,
                                            survey_item=survey_item,
                                            unadapted_chat_history= st.session_state.messages,
                                            unadapted_response=unada_bot_response)

        # Stream the response to the chat using `st.write_stream`, then store it in 
        # session state.
        with st.chat_message("assistant"):
            response = st.write("**Unadapted response**: ", unada_bot_response)
            response = st.write("**Adapted response**: ", ada_response)
        st.session_state.messages.append({"role": "assistant", "content": unada_bot_response})