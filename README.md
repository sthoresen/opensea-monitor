# opensea-monitor

## Overview
This project is designed to monitor OpenSea for new activity in a specified marketplace. It provides real-time email notifications for new sales, changes in floor prices, or when the best offer changes by a minimum threshold.

## Components
- `monitorNOAZ.py`: Contains the core Python logic and API calls to the OpenSea API.
- `function_app.py`: Integrates the monitoring logic into an Azure Function for deployment on Azure Cloud. The function is triggered every 10 seconds using a CRON expression.

## Features
- **Email Notifications**: Utilizes Mailjet to send alerts about significant marketplace events.
- **Data Gathering**: Leverages the OpenSea API to fetch real-time data.
- **Hosting**: Optionally hosted on Azure to run as a serverless function.

## Usage

### Setup
1. **Environment Setup**: Create a `.env` file in the project root to store sensitive data like API keys. Refer to `.env.example` for the required format.

### Running Locally
- Execute `python monitorNOAZ.py` to run the monitoring logic locally.

### Deployment on Azure
- Deploy the project to Azure as a function app.

## Configuration
- **CRON Schedule**: The function app uses a CRON schedule set to execute every 10 seconds.
- **Email Service Configuration**: Set up your Mailjet account and configure the API keys in the `.env` file as per the instructions in `.env.example`.
