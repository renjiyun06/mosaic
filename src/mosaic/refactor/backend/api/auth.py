"""Authentication-related API endpoints"""
from fastapi import APIRouter, HTTPException, status
from .deps import SessionDep, CurrentUser
from ..schemas.auth import (
    SendCodeRequest,
    SendCodeResponse,
    RegisterRequest,
    RegisterResponse,
    LoginRequest,
    LoginResponse,
    UserResponse,
    UpdateProfileRequest,
    UpdateProfileResponse,
    ChangePasswordRequest,
    ChangePasswordResponse,
)
from ..services import AuthService
from ..exceptions import MosaicException
from ..logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/send-code",
    response_model=SendCodeResponse,
    summary="Send verification code",
)
async def send_verification_code(
    request: SendCodeRequest,
    session: SessionDep,
) -> SendCodeResponse:
    """Send email verification code

    Send a 6-digit verification code to the specified email address
    for registration verification.

    - **email**: Email address
    """
    try:
        logger.info(f"API: Sending verification code to {request.email}")
        return await AuthService.send_verification_code(session, request)
    except MosaicException as e:
        logger.error(
            f"Failed to send verification code: {e.message}"
        )
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post(
    "/register",
    response_model=RegisterResponse,
    summary="User registration",
)
async def register(
    request: RegisterRequest,
    session: SessionDep,
) -> RegisterResponse:
    """User registration

    Register a new account using email verification code.
    Must call send-code endpoint first.

    - **username**: Username (3-50 chars, letters/numbers/underscores/hyphens only)
    - **email**: Email address
    - **password**: Password (at least 8 characters)
    - **verification_code**: Email verification code (6 digits)
    """
    try:
        logger.info(
            f"API: Registering user {request.username} "
            f"with email {request.email}"
        )
        return await AuthService.register(session, request)
    except MosaicException as e:
        logger.error(
            f"Registration failed for {request.username}: {e.message}"
        )
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="User login",
)
async def login(
    request: LoginRequest,
    session: SessionDep,
) -> LoginResponse:
    """User login

    Login with username/email and password, returns JWT access token.

    - **username_or_email**: Username or email address
    - **password**: Password
    """
    try:
        logger.info(
            f"API: Login attempt for {request.username_or_email}"
        )
        return await AuthService.login(session, request)
    except MosaicException as e:
        logger.error(
            f"Login failed for {request.username_or_email}: {e.message}"
        )
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user info",
)
async def get_current_user_info(
    current_user: CurrentUser,
) -> UserResponse:
    """Get current authenticated user information

    Requires JWT token in request header:
    ```
    Authorization: Bearer <token>
    ```
    """
    logger.debug(
        f"API: Getting user info for {current_user.username}"
    )
    return UserResponse.model_validate(current_user)


@router.patch(
    "/me",
    response_model=UpdateProfileResponse,
    summary="Update current user profile",
)
async def update_current_user_profile(
    request: UpdateProfileRequest,
    session: SessionDep,
    current_user: CurrentUser,
) -> UpdateProfileResponse:
    """Update current user profile

    Update profile information (currently only avatar URL).
    Username and email cannot be changed.

    Requires JWT token in request header:
    ```
    Authorization: Bearer <token>
    ```

    - **avatar_url**: Avatar image URL (optional)
    """
    try:
        logger.info(
            f"API: Updating profile for user {current_user.username}"
        )
        return await AuthService.update_profile(session, current_user, request)
    except MosaicException as e:
        logger.error(
            f"Failed to update profile for {current_user.username}: {e.message}"
        )
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post(
    "/change-password",
    response_model=ChangePasswordResponse,
    summary="Change password",
)
async def change_password(
    request: ChangePasswordRequest,
    session: SessionDep,
    current_user: CurrentUser,
) -> ChangePasswordResponse:
    """Change user password

    Change password by providing current password and new password.

    Requires JWT token in request header:
    ```
    Authorization: Bearer <token>
    ```

    - **current_password**: Current password (for verification)
    - **new_password**: New password (must be different from current)
    """
    try:
        logger.info(
            f"API: Changing password for user {current_user.username}"
        )
        return await AuthService.change_password(session, current_user, request)
    except MosaicException as e:
        logger.error(
            f"Failed to change password for {current_user.username}: {e.message}"
        )
        raise HTTPException(status_code=e.status_code, detail=e.message)
