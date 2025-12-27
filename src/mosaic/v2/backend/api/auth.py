"""Authentication API endpoints"""

import random
import smtplib
import logging
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Annotated

from ..schema.response import SuccessResponse
from ..schema.auth import (
    SendCodeRequest,
    RegisterRequest,
    LoginRequest,
    AuthResponse,
    UserOut,
)
from ..model import User, EmailVerification
from ..dep import get_db_session, get_current_user
from ..exception import ConflictError, InternalError, ValidationError, AuthenticationError
from ..security import get_password_hash, verify_password, create_access_token

logger = logging.getLogger(__name__)

# Router configuration
router = APIRouter(prefix="/auth", tags=["Authentication"])


# ==================== Type Aliases ====================

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


# ==================== Email Sending Helper ====================

def send_email(
    to_email: str,
    subject: str,
    body: str,
    smtp_config: dict,
) -> None:
    """Send email via SMTP

    Args:
        to_email: Recipient email address
        subject: Email subject
        body: Email body (plain text)
        smtp_config: SMTP configuration dict with keys:
            - smtp_host: SMTP server address
            - smtp_port: SMTP server port
            - use_ssl: Whether to use SSL
            - sender_email: Sender email address
            - sender_password: Sender email password (auth code)
            - sender_name: Sender display name (optional)

    Raises:
        Exception: Failed to send email
    """
    try:
        # Create message
        msg = MIMEMultipart()
        sender_name = smtp_config.get("sender_name", "Mosaic System")
        msg["From"] = f"{sender_name} <{smtp_config['sender_email']}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        # Connect and send
        use_ssl = smtp_config.get("use_ssl", False)

        if use_ssl:
            server = smtplib.SMTP_SSL(smtp_config["smtp_host"], smtp_config["smtp_port"])
        else:
            server = smtplib.SMTP(smtp_config["smtp_host"], smtp_config["smtp_port"])
            server.starttls()

        server.login(smtp_config["sender_email"], smtp_config["sender_password"])
        server.send_message(msg)
        server.close()

        logger.info(f"Email sent successfully to {to_email}")

    except Exception as e:
        logger.exception(f"Failed to send email to {to_email}")
        raise


@router.post(
    "/send-code",
    response_model=SuccessResponse[None],
    summary="Send verification code",
    description="""
    Send a 6-digit verification code to the email address for registration.

    **Flow:**
    1. Validate email format
    2. Check if email is already registered
    3. Generate random 6-digit verification code
    4. Save code to database with expiration time (default 10 minutes)
    5. Send email with verification code
    6. Return success response

    **Returns:**
    - success: true
    - data: null
    - message: "Verification code sent to {email}"

    **Errors:**
    - 200 + success=false + VALIDATION_ERROR: Invalid email format
    - 200 + success=false + CONFLICT: Email already registered
    - 200 + success=false + INTERNAL_ERROR: Failed to send email
    """
)
async def send_verification_code(
    request: SendCodeRequest,
    req: Request,
    session: SessionDep,
):
    """Send email verification code

    Args:
        request: Send code request (email)
        req: FastAPI request object (to access app state/config)
        session: Database session (injected via dependency)

    Returns:
        SuccessResponse[None]: Success message

    Raises:
        ConflictError: Email already registered
        InternalError: Failed to send email
    """
    # Get email config from app state
    email_config = req.app.state.config["email"]

    # 1. Check if email already registered
    stmt = select(User).where(User.email == request.email, User.deleted_at.is_(None))
    result = await session.execute(stmt)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        logger.warning(f"Email already registered: {request.email}")
        raise ConflictError("Email already registered")

    # 2. Generate 6-digit verification code
    code = f"{random.randint(0, 999999):06d}"

    # 3. Calculate expiration time (10 minutes from now)
    expires_at = datetime.now() + timedelta(minutes=10)

    # 4. Save verification code to database
    verification = EmailVerification(
        email=request.email,
        code=code,
        expires_at=expires_at,
        is_used=False,
    )
    session.add(verification)
    await session.commit()

    logger.info(f"Verification code generated for {request.email}: {code}")

    # 5. Send email
    subject = "Mosaic - Email Verification Code"
    body = f"""Hello,

Your verification code is: {code}

This code will expire in 10 minutes.

If you did not request this code, please ignore this email.

Best regards,
Mosaic Team
"""

    try:
        send_email(
            to_email=request.email,
            subject=subject,
            body=body,
            smtp_config=email_config,
        )
    except Exception as e:
        logger.exception(f"Failed to send verification code to {request.email}")
        raise InternalError(f"Failed to send email: {str(e)}")

    # 6. Return success response
    return SuccessResponse(
        data=None,
        message=f"Verification code sent to {request.email}"
    )


@router.post(
    "/register",
    response_model=SuccessResponse[AuthResponse],
    summary="User registration",
    description="""
    Register a new user account.

    **Prerequisites:**
    Must call `/auth/send-code` endpoint first to receive verification code.

    **Flow:**
    1. Validate request format (username, email, password, verification_code)
    2. Verify the verification code (check if valid and not expired)
    3. Check if username already exists
    4. Check if email already exists
    5. Hash password using bcrypt (with SHA256 normalization)
    6. Create user record in database
    7. Mark verification code as used
    8. Create user directory: {instance_path}/users/{user_id}/
    9. Generate JWT access token
    10. Return user info and token

    **Returns:**
    - success: true
    - data: AuthResponse (user info + access_token)
    - message: "Registration successful"

    **Errors:**
    - 200 + success=false + VALIDATION_ERROR: Invalid input format or verification code invalid/expired
    - 200 + success=false + CONFLICT: Username or email already exists
    """
)
async def register(
    request: RegisterRequest,
    req: Request,
    session: SessionDep,
):
    """Register a new user account

    Args:
        request: Registration request (username, email, password, verification_code)
        req: FastAPI request object (to access app state)
        session: Database session (injected)

    Returns:
        SuccessResponse[AuthResponse]: User info and JWT token

    Raises:
        ValidationError: Invalid input format or verification code invalid/expired
        ConflictError: Username or email already exists
    """
    # 1. Verify email verification code
    stmt = select(EmailVerification).where(
        EmailVerification.email == request.email,
        EmailVerification.code == request.verification_code,
        EmailVerification.is_used == False,
        EmailVerification.expires_at > datetime.now(),
    )
    result = await session.execute(stmt)
    verification = result.scalar_one_or_none()

    if not verification:
        logger.warning(f"Invalid or expired verification code for {request.email}")
        raise ValidationError("Invalid or expired verification code")

    # 2. Check if username already exists
    stmt = select(User).where(User.username == request.username, User.deleted_at.is_(None))
    result = await session.execute(stmt)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        logger.warning(f"Username already exists: {request.username}")
        raise ConflictError("Username already exists")

    # 3. Check if email already exists (double check)
    stmt = select(User).where(User.email == request.email, User.deleted_at.is_(None))
    result = await session.execute(stmt)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        logger.warning(f"Email already exists: {request.email}")
        raise ConflictError("Email already exists")

    # 4. Hash password
    password_hash = get_password_hash(request.password)

    # 5. Create user
    user = User(
        username=request.username,
        email=request.email,
        hashed_password=password_hash,
        is_active=True,
    )
    session.add(user)
    await session.flush()  # Flush to get user.id

    # 6. Mark verification code as used
    verification.is_used = True
    session.add(verification)

    # 7. Commit transaction
    await session.commit()

    logger.info(f"User registered successfully: {user.email} (id={user.id})")

    # 8. Create user directory
    try:
        instance_path = req.app.state.instance_path
        user_dir = instance_path / "users" / str(user.id)
        user_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created user directory: {user_dir}")
    except Exception as e:
        logger.error(f"Failed to create user directory for {user.id}: {e}")
        # Don't fail registration if directory creation fails

    # 9. Generate JWT token
    jwt_config = req.app.state.config["jwt"]
    access_token = create_access_token(user.id, jwt_config)

    # 10. Convert user to UserOut
    user_out = UserOut.model_validate(user)

    # 11. Return response
    return SuccessResponse(
        data=AuthResponse(user=user_out, access_token=access_token),
        message="Registration successful"
    )


@router.post(
    "/login",
    response_model=SuccessResponse[AuthResponse],
    summary="User login",
    description="""
    Login with username/email and password.

    **Flow:**
    1. Validate request format
    2. Find user by username OR email (supports both)
    3. Verify password using bcrypt
    4. Check if account is active (is_active=true)
    5. Generate JWT access token (payload: {sub: user_id, exp: timestamp})
    6. Return user info and token

    **Returns:**
    - success: true
    - data: AuthResponse (user info + access_token)
    - message: null

    **Errors:**
    - 200 + success=false + AUTHENTICATION_ERROR: Invalid username/email or password
    - 200 + success=false + VALIDATION_ERROR: Account disabled
    """
)
async def login(
    request: LoginRequest,
    req: Request,
    session: SessionDep,
):
    """User login

    Args:
        request: Login request (username_or_email, password)
        req: FastAPI request object (to access app state)
        session: Database session (injected)

    Returns:
        SuccessResponse[AuthResponse]: User info and JWT token

    Raises:
        AuthenticationError: Invalid credentials
        ValidationError: Account disabled
    """
    # 1. Find user by username or email
    stmt = select(User).where(
        (User.username == request.username_or_email) | (User.email == request.username_or_email),
        User.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    # 2. Check if user exists
    if not user:
        logger.warning(f"Login attempt with non-existent user: {request.username_or_email}")
        raise AuthenticationError("Invalid credentials")

    # 3. Verify password
    if not verify_password(request.password, user.hashed_password):
        logger.warning(f"Login attempt with wrong password for user: {user.email}")
        raise AuthenticationError("Invalid credentials")

    # 4. Check if account is active
    if not user.is_active:
        logger.warning(f"Login attempt for inactive account: {user.email}")
        raise ValidationError("Account is disabled")

    logger.info(f"User logged in successfully: {user.email} (id={user.id})")

    # 5. Generate JWT token
    jwt_config = req.app.state.config["jwt"]
    access_token = create_access_token(user.id, jwt_config)

    # 6. Convert user to UserOut
    user_out = UserOut.model_validate(user)

    # 7. Return response
    return SuccessResponse(
        data=AuthResponse(user=user_out, access_token=access_token),
        message=None
    )


@router.post(
    "/logout",
    response_model=SuccessResponse[None],
    summary="User logout",
    description="""
    Logout current user (stateless, mainly for client-side cleanup).

    **Flow:**
    1. Validate JWT token from Authorization header (optional)
    2. Return success response
    3. Client clears token from localStorage

    **Note:**
    - JWT tokens are stateless, server doesn't track sessions
    - This endpoint mainly signals client to clear local token
    - Token blacklist is NOT implemented (can be added later if needed)

    **Returns:**
    - success: true
    - data: null
    - message: "Logout successful"
    """
)
async def logout():
    """User logout

    Returns:
        SuccessResponse[None]: Success message

    Note:
        Since JWT is stateless, logout is mainly for client-side token cleanup.
        Server doesn't maintain session state or token blacklist.
        This endpoint exists for API consistency and to signal the client
        to clear local authentication state.
    """
    # JWT is stateless, no server-side action needed
    # Client should clear token from localStorage/sessionStorage
    logger.debug("Logout endpoint called")
    return SuccessResponse(data=None, message="Logout successful")


@router.get(
    "/me",
    response_model=SuccessResponse[UserOut],
    summary="Get current user info",
    description="""
    Get current authenticated user information.

    **Flow:**
    1. Extract JWT token from Authorization header
    2. Decode and validate token
    3. Get user_id from token payload
    4. Query user from database
    5. Return user info

    **Authentication:**
    Requires JWT token in request header:
    ```
    Authorization: Bearer <token>
    ```

    **Returns:**
    - success: true
    - data: UserOut (user information)
    - message: null

    **Errors:**
    - 200 + success=false + AUTHENTICATION_ERROR: Invalid or expired token
    - 200 + success=false + NOT_FOUND: User not found
    """
)
async def get_current_user_info(
    current_user: CurrentUserDep,
):
    """Get current authenticated user information

    Args:
        current_user: Current user (injected from JWT token)

    Returns:
        SuccessResponse[UserOut]: User information

    Raises:
        AuthenticationError: Invalid or expired token
        NotFoundError: User not found
    """
    # 1. Current user is already injected by dependency
    # 2. Convert to UserOut schema
    user_out = UserOut.model_validate(current_user)

    # 3. Return response
    return SuccessResponse(data=user_out, message=None)
