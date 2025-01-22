# User Profile API

![Python](https://img.shields.io/badge/python-v3.7+-blue.svg)
![Django](https://img.shields.io/badge/django-3.2+-green.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](http://makeapullrequest.com)
![Last Commit](https://img.shields.io/github/last-commit/MESH-Research/knowledge-commons-profiles)


**This project is a work in progress and not complete.** 

This project provides an API endpoint to retrieve detailed information about users in our system.

## Features

- Retrieves comprehensive user information including:
  - Personal details (name, title, affiliation)
  - Academic background and interests
  - Publications and projects
  - Social media handles and website URLs
  - Commons activity and memberships
  - And more...

## Installation

1. Clone this repository:

This project provides an API endpoint to retrieve detailed information about users in our system.

## Features

- Retrieves comprehensive user information including:
  - Personal details (name, title, affiliation)
  - Academic background and interests
  - Publications and projects
  - Social media handles and website URLs
  - Commons activity and memberships
  - And more...

## Installation

1. Clone this repository:
    git clone https://github.com/yourusername/user-profile-api.git

2. Navigate to the project directory:
    cd user-profile-api

3. Install the required dependencies:
    pip install -r requirements.txt

## Usage

The main function `get_about_user(request, user)` can be used as follows:

```python
from user_profile import get_about_user

# Assuming you have a request object and a user object
user_info = get_about_user(request, user)
```

This will return a dictionary containing all available information about the user.

## API Endpoint
The API endpoint can be accessed at:

    GET /api/user/<user_id>/about

Replace <user_id> with the ID of the user you want to retrieve information for.

## Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

## License
This project is licensed under the MIT License - see the LICENSE.md file for details.

