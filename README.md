# AI-Glasses: An AI-Powered Augmented Reality System

[**[Project Page]**](https://kylechen.top/Project/AI_Glasses.html/) &ensp; [**[Paper]**](https://arxiv.org/abs/2601.06235) &ensp; [**[PPT]**](https://kylechen.top/Reference/NCHC/Glasses_PPT.pdf)

This project is an AI-powered augmented reality (AR) system designed to provide a seamless and intelligent user experience through AR glasses. The system can process voice commands, understand user intent, and perform various tasks, such as providing information, controlling devices, and interacting with the digital world.

## Architecture

The system is built on a microservices-based architecture, with several key components working together to provide a robust and scalable solution.

-   **AR System Manager (`ar_system_manager.py`)**: The main orchestrator of the AR system. It manages the flow from the AR glasses' RTSP stream, through the ASR (Automatic Speech Recognition) and AI agents, to task execution.

-   **AI Orchestrator (`orchestrator.py`)**: The core of the AI system. It coordinates the LLMs (Large Language Models), MCP (Model Context Protocol) tools, and RAG (Retrieval-Augmented Generation) memory to understand user queries and generate intelligent responses.

-   **LLM Manager (`llm_manager.py`)**: Manages the interactions with local language models through Ollama, enabling the system to generate human-like text and understand natural language.

-   **RTSP Manager (`rtsp_manager.py` and `network_rtsp_manager.py`)**: Handles the real-time streaming protocol (RTSP) streams from the AR glasses, allowing the system to process audio and video data in real-time.

-   **Task Executor (`task_executor.py`)**: Executes the tasks determined by the AI orchestrator, such as displaying information, controlling devices, or interacting with other systems.

-   **RabbitMQ Client (`rabbitmq_client.py`)**: Manages the communication between the different microservices, ensuring reliable and asynchronous message passing.

## Core Functionalities

-   **Voice Command Processing**: The system can process voice commands from the user through the AR glasses, allowing for a hands-free and intuitive user interface.

-   **AI-Based Responses**: The system uses advanced AI models to understand user intent and provide intelligent and context-aware responses.

-   **Task Execution**: The system can perform a wide range of tasks, such as searching the web, providing stock information, and controlling smart devices.

## Getting Started

To get started with the AI-Glasses project, you'll need to have Docker and Python installed on your system.

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/your-username/AI-Glasses.git
    ```

2.  **Install the required Python packages**:
    ```bash
    pip install -r ai_system/requirements.txt
    ```

3.  **Set up the environment variables**:
    Create a `.env` file in the `ai_system` directory and add the required environment variables.

4.  **Run the system using Docker Compose**:
    ```bash
    docker-compose up -d
    ```

## Key Technologies

-   **Python**: The primary programming language used in the project.
-   **Docker**: For containerizing the application and its dependencies.
-   **RabbitMQ**: For asynchronous communication between microservices.
-   **Ollama**: For running local large language models.
-   **OpenCV**: For processing video streams.
-   **aiohttp**: For making asynchronous HTTP requests.
-   **Pika**: For interacting with RabbitMQ.
