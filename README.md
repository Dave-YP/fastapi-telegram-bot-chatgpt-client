# ChatGPT API Client using FastAPI with Web Interface and Telegram Bot Integration (lite version)

<img src="./app/static/main.png" alt="Project Screenshot" class="responsive-img">
<img src="./app/static/chat.png" alt="Project Screenshot" class="responsive-img">
<img src="./app/static/tg.png" alt="Project Screenshot" class="responsive-img">

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Telegram](https://img.shields.io/badge/Telegram-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-336791?style=for-the-badge&logo=postgresql&logoColor=white)

## Description

This project is a FastAPI-powered client that connects with the OpenAI ChatGPT API, featuring both a web interface and a Telegram bot for seamless interaction.
Users can register, log in, and chat with ChatGPT either through the web interface or the Telegram bot, while keeping their sessions authenticated.

Key features include a token-based currency system, where users receive an initial allocation of tokens upon registration.
These tokens are consumed based on the number of characters in both incoming and outgoing messages during conversations.
The project also includes a daily message limit and the ability to save conversation context with the ChatGPT API across both platforms.
On the website, users can manage multiple chat tabs, each with its own editable title, allowing for easy organization and identification of different conversations.
Each tab maintains its own context, even across sessions.
Additionally, users can delete their chat history and context both through the Telegram bot and the web interface.

This version emphasizes the role of FastAPI as the backbone of the client connecting to the ChatGPT API, while also highlighting the flexibility and features offered by the web interface and Telegram bot.

## Key Features

- User registration and authentication system
- Web interface for account management
- Smooth transition from the web interface to the Telegram bot for authenticated users
- Integration with OpenAI's ChatGPT API
- Token-based currency system where tokens are earned upon registration and consumed based on the number of characters used in dialogues
- Daily message limit for users
- Ability to open a chat with GPT on the website
- Support for context in the dialogue
- Manage multiple chat tabs with editable titles on the website
- Configurable maximum number of messages in the context

## Main Components

- **PostgreSQL**: Stores user data, context, and manages authentication.
- **Redis**: Handles caching and user session management.
- **FastAPI Service**: Processes requests from both the web interface and the Telegram bot.
- **Telegram Bot**: Provides a chat interface for users to interact with ChatGPT.
- **Web Interface**: Allows users to register, log in, access the site and bot chat, and manage chat tabs.

## Requirements

- Docker
- Docker Compose
- OpenAI API key
- Telegram bot token

## Installation and Setup

1. Clone the repository:

   ```bash
   git clone https://github.com/Dave-YP/fastapi-telegram-bot-chatgpt.git
   cd fastapi-telegram-bot-chatgpt
    ```

2. Configure environment variables:
    Create a `.env` file in the root of the project and add the following variables:

    ```env
    OPENAI_API_KEY=your_openai_api_key
    DATABASE_URL=postgresql+asyncpg://user:password@localhost/dbname
    TELEGRAM_TOKEN=your_telegram_bot_token
    API_URL=http://fastapi:5000
    DAILY_MESSAGE_LIMIT=100
    SECRET_KEY=your_jwt_secret_key
    TELEGRAM_BOT_URL=https://t.me/your_bot_username
    MAX_CONTEXT_MESSAGES=50
    ```

3. Build and start the containers:

    ```bash
    docker-compose up --build
    ```

## Usage

1. **Web Interface**:
    Open your browser and go to <http://localhost:5000>.
    Register a new account or log in to an existing one.
    After logging in, you will receive a link to the Telegram bot.

2. **Telegram Bot**:
    Follow the provided link or find your bot in Telegram.
    Start chatting with the bot - you will be automatically authenticated.

3. **Ask Questions**:
    Simply send text messages to the bot with your questions.
    The bot will forward them to the FastAPI service, which will then request a response from the OpenAI API.

## Project Structure

- **app/main.py**: The main file of the FastAPI service.
- **app/api/endpoints.py**: Routes of the FastAPI service that handle requests and interact with the OpenAI API.
- **app/bot/telegram_bot.py**: Implementation of the Telegram bot.
- **app/db/models.py**: Database models.
- **app/db/init_db.py**: Database initialization.
- **app/services/auth.py**: Authentication services.
- **app/services/openai_service.py**: Services for interacting with OpenAI.
- **app/services/token_service.py**: Services for managing tokens.
- **app/services/message_limit.py**: Services for managing message limits.
- **app/schemas/user.py**: Pydantic models for users.
- **app/schemas/token.py**: Pydantic models for tokens.
- **app/core/config.py**: Application configuration.
- **app/core/status_codes.py**: Error messages and status codes.
- **app/templates/**: HTML templates for the web interface.
- **chat.html**: Chat template.
- **index.html**: Main page.
- **login.html**: Login page.
- **register.html**: Registration page.
- **app/static/**: Static files for the web interface.
- **chat.js**: JavaScript file for the chat.
- **style.css**: CSS file for styles.
- **Dockerfile.fastapi**: Dockerfile for the FastAPI service.
- **Dockerfile.bot**: Dockerfile for the Telegram bot.
- **docker-compose.yml**: Docker Compose configuration.

## License

This project is licensed under the GNU General Public License (GPL). See the LICENSE file for details.

## Configuration and Limits

- **DAILY_MESSAGE_LIMIT**: The number of questions a user can ask per day. The default value is 100.
- **SECRET_KEY**: Used to encrypt the JWT token (ensure it is secure and unique).
- **MAX_CONTEXT_MESSAGES**: The number of recent messages saved in the context. The default value is 50.

## Contact

If you encounter any issues or have questions, please create an issue in the GitHub repository or contact the project author.
