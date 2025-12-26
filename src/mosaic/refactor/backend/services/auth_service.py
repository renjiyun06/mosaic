"""Authentication service"""
import secrets
import string
from pathlib import Path
from datetime import datetime, timedelta
from sqlmodel import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from ..config import settings, get_instance_path
from ..models import User, EmailVerification
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
from ..auth import (
    verify_password,
    get_password_hash,
    create_access_token,
)
from ..utils.email import EmailService
from ..utils.query import get_active_query
from ..exceptions import (
    ValidationError,
    ConflictError,
    AuthenticationError,
    NotFoundError,
)
from ..logger import get_logger

logger = get_logger(__name__)


class AuthService:
    """Authentication service"""

    @staticmethod
    def _generate_verification_code() -> str:
        """Generate random verification code"""
        return "".join(
            secrets.choice(string.digits)
            for _ in range(settings.verification_code_length)
        )

    @staticmethod
    def _create_user_directory(user_id: int) -> None:
        """Create user directory in instance path

        Args:
            user_id: User ID

        Creates:
            {instance_path}/users/{user_id}/
        """
        try:
            instance_path = get_instance_path()
            user_dir = instance_path / "users" / str(user_id)
            user_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created user directory: {user_dir}")
        except Exception as e:
            logger.error(f"Failed to create user directory for user {user_id}: {e}")
            # Don't fail the registration if directory creation fails
            # This is a filesystem operation that shouldn't block user creation

    @staticmethod
    async def send_verification_code(
        session: AsyncSession,
        request: SendCodeRequest,
    ) -> SendCodeResponse:
        """Send verification code

        Args:
            session: Database session
            request: Send code request

        Returns:
            Send code response

        Raises:
            ConflictError: Email already registered
        """
        logger.info(f"Sending verification code to {request.email}")

        # 1. Check if email is already registered
        query = get_active_query(User).where(User.email == request.email)
        result = await session.execute(query)
        existing_user = result.scalar_one_or_none()
        if existing_user:
            logger.warning(
                f"Email already registered: {request.email}"
            )
            raise ConflictError("Email already registered")

        # 2. Generate verification code
        code = AuthService._generate_verification_code()
        expires_at = datetime.now() + timedelta(
            minutes=settings.verification_code_expire_minutes
        )

        logger.debug(
            f"Generated verification code for {request.email}, "
            f"expires at {expires_at}"
        )

        # 3. Save to database
        verification = EmailVerification(
            email=request.email,
            code=code,
            expires_at=expires_at,
            is_used=False,
        )
        session.add(verification)
        await session.commit()

        # 4. Send email
        EmailService.send_verification_code(request.email, code)

        logger.info(
            f"Verification code sent successfully to {request.email}"
        )

        return SendCodeResponse(
            message="Verification code sent, please check your email",
            expires_at=expires_at,
        )

    @staticmethod
    async def register(
        session: AsyncSession,
        request: RegisterRequest,
    ) -> RegisterResponse:
        """User registration

        Args:
            session: Database session
            request: Registration request

        Returns:
            Registration response

        Raises:
            ConflictError: Username or email already exists
            ValidationError: Verification code invalid or expired
        """
        logger.info(
            f"Processing registration for username: {request.username}, "
            f"email: {request.email}"
        )

        # 1. Verify verification code
        query = (
            get_active_query(EmailVerification)
            .where(EmailVerification.email == request.email)
            .where(EmailVerification.code == request.verification_code)
            .where(EmailVerification.is_used == False)  # noqa: E712
            .where(EmailVerification.expires_at > datetime.now())
        )
        result = await session.execute(query)
        verification = result.scalar_one_or_none()

        if not verification:
            logger.warning(
                f"Invalid or expired verification code for {request.email}"
            )
            raise ValidationError(
                "Verification code invalid or expired"
            )

        # 2. Check if username already exists
        username_query = get_active_query(User).where(
            User.username == request.username
        )
        username_result = await session.execute(username_query)
        if username_result.scalar_one_or_none():
            logger.warning(
                f"Username already exists: {request.username}"
            )
            raise ConflictError("Username already exists")

        # 3. Check if email already exists
        # (should not happen as code was verified)
        email_query = get_active_query(User).where(
            User.email == request.email
        )
        email_result = await session.execute(email_query)
        if email_result.scalar_one_or_none():
            logger.warning(
                f"Email already registered: {request.email}"
            )
            raise ConflictError("Email already registered")

        # 4. Create user
        user = User(
            username=request.username,
            email=request.email,
            hashed_password=get_password_hash(request.password),
            is_active=True,
            is_verified=True,  # Verified via email code
        )
        session.add(user)

        # 5. Mark verification code as used
        verification.is_used = True
        session.add(verification)

        await session.commit()
        await session.refresh(user)

        logger.info(
            f"User registered successfully: {request.username} "
            f"(ID: {user.id})"
        )

        # 6. Create user directory in filesystem
        AuthService._create_user_directory(user.id)

        return RegisterResponse(
            message="Registration successful",
            user=UserResponse.model_validate(user),
        )

    @staticmethod
    async def login(
        session: AsyncSession,
        request: LoginRequest,
    ) -> LoginResponse:
        """User login

        Args:
            session: Database session
            request: Login request

        Returns:
            Login response with JWT token

        Raises:
            AuthenticationError: Invalid username/email or password
            ValidationError: Account disabled or not verified
        """
        logger.info(
            f"Login attempt for: {request.username_or_email}"
        )

        # 1. Find user (supports username or email login)
        query = get_active_query(User).where(
            or_(
                User.username == request.username_or_email,
                User.email == request.username_or_email,
            )
        )
        result = await session.execute(query)
        user = result.scalar_one_or_none()

        if not user:
            logger.warning(
                f"User not found: {request.username_or_email}"
            )
            raise AuthenticationError(
                "Invalid username/email or password"
            )

        # 2. Verify password
        if not verify_password(request.password, user.hashed_password):
            logger.warning(
                f"Invalid password for user: {user.username}"
            )
            raise AuthenticationError(
                "Invalid username/email or password"
            )

        # 3. Check account status
        if not user.is_active:
            logger.warning(
                f"Account disabled: {user.username}"
            )
            raise ValidationError(
                "Account disabled, please contact administrator"
            )

        if not user.is_verified:
            logger.warning(
                f"Account not verified: {user.username}"
            )
            raise ValidationError(
                "Account not verified, please verify your email first"
            )

        # 4. Generate JWT token
        access_token = create_access_token(data={"sub": str(user.id)})

        logger.info(
            f"User logged in successfully: {user.username} (ID: {user.id})"
        )

        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            user=UserResponse.model_validate(user),
        )

    @staticmethod
    async def update_profile(
        session: AsyncSession,
        user: User,
        request: UpdateProfileRequest,
    ) -> UpdateProfileResponse:
        """Update user profile

        Args:
            session: Database session
            user: Current user
            request: Update profile request

        Returns:
            Update profile response

        Raises:
            ValidationError: Invalid avatar URL
        """
        logger.info(f"Updating profile for user: {user.username}")

        # Update avatar URL (only field that can be updated)
        # Validate URL format if provided (not empty)
        if request.avatar_url and not request.avatar_url.startswith(("http://", "https://")):
            raise ValidationError("Avatar URL must start with http:// or https://")

        # Update avatar (allows setting to None to clear avatar)
        user.avatar_url = request.avatar_url
        logger.debug(f"Updated avatar URL for user {user.username}: {request.avatar_url}")

        session.add(user)
        await session.commit()
        await session.refresh(user)

        logger.info(f"Profile updated successfully for user: {user.username}")

        return UpdateProfileResponse(
            message="Profile updated successfully",
            user=UserResponse.model_validate(user),
        )

    @staticmethod
    async def change_password(
        session: AsyncSession,
        user: User,
        request: ChangePasswordRequest,
    ) -> ChangePasswordResponse:
        """Change user password

        Args:
            session: Database session
            user: Current user
            request: Change password request

        Returns:
            Change password response

        Raises:
            AuthenticationError: Current password is incorrect
            ValidationError: New password is invalid
        """
        logger.info(f"Changing password for user: {user.username}")

        # Verify current password
        if not verify_password(request.current_password, user.hashed_password):
            logger.warning(f"Incorrect current password for user: {user.username}")
            raise AuthenticationError("Current password is incorrect")

        # Update password
        user.hashed_password = get_password_hash(request.new_password)
        session.add(user)
        await session.commit()

        logger.info(f"Password changed successfully for user: {user.username}")

        return ChangePasswordResponse(
            message="Password changed successfully"
        )
