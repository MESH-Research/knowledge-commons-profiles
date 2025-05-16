class RESTError:
    NON_FATAL_NO_MYSQL_SILENT_FIELDS_MISSING = {
        "message": "Database not accessible. Some fields may be "
        "silently missing",
        "status": "non-fatal",
        "code": 1001,
    }
    NON_FATAL_UNDEFINED_ERROR = {
        "message": "Undefined error",
        "status": "non-fatal",
        "code": 1002,
    }
    FATAL_NO_USERNAME_DEFINED = {
        "message": "No username defined",
        "status": "fatal",
        "code": 1003,
    }
    FATAL_NO_GROUP_ID_OR_SLUG = {
        "message": "No group ID or slug defined",
        "status": "fatal",
        "code": 1004,
    }
    FATAL_USER_NOT_FOUND = {
        "message": "User not found",
        "status": "fatal",
        "code": 1005,
    }
    FATAL_UNDEFINED_ERROR = {
        "message": "Undefined error",
        "status": "fatal",
        "code": 1006,
    }
    FATAL_GROUP_NOT_FOUND = {
        "message": "Group not found",
        "status": "fatal",
        "code": 1007,
    }
    FATAL_NO_SUB = {
        "message": "Sub not specified",
        "status": "fatal",
        "code": 1008,
    }
