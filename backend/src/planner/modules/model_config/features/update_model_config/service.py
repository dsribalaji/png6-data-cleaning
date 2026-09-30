"""Service for updating the model configuration."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.audit import record_audit
from planner.modules.model_config.crypto import credential_last4, encrypt_credential
from planner.modules.model_config.features.get_model_config.schemas import ModelConfigOut
from planner.modules.model_config.features.update_model_config.schemas import UpdateModelConfigInput
from planner.modules.model_config.models import ModelConfig


async def update_model_config(
    session: AsyncSession,
    input: UpdateModelConfigInput,
    *,
    actor_id: UUID | None = None,
    actor_role: str = "system",
) -> ModelConfigOut:
    """Update or initialize the active model configuration in a single transaction.

    Encrypts the write-only credential if provided, deactivates previous rows,
    activates the new row, and records an audit event.
    """
    # 1. Load active row if present
    stmt = select(ModelConfig).where(ModelConfig.is_active.is_(True))
    result = await session.execute(stmt)
    active_row = result.scalar_one_or_none()

    # 2. Determine credentials
    if input.credential is not None:
        if input.credential.strip():
            ciphertext = encrypt_credential(input.credential.strip())
            last4 = credential_last4(input.credential.strip())
        else:
            ciphertext = None
            last4 = None
    elif active_row is not None:
        ciphertext = active_row.credential_ciphertext
        last4 = active_row.credential_last4
    else:
        ciphertext = None
        last4 = None

    # 3. Deactivate any existing active rows
    await session.execute(
        update(ModelConfig).where(ModelConfig.is_active.is_(True)).values(is_active=False)
    )

    # 4. Create new active row
    new_config = ModelConfig(
        provider=input.provider,
        model=input.model,
        endpoint_url=input.endpoint_url,
        credential_ciphertext=ciphertext,
        credential_last4=last4,
        allow_data_sharing=input.allow_data_sharing,
        is_active=True,
        updated_by=actor_id,
    )
    session.add(new_config)
    await session.flush()

    # 5. Record audit event
    # NOTE: record_audit is currently a not-started stub owned by worker W1; wired per specification
    await record_audit(
        user_id=actor_id,
        user_role=actor_role,
        event_type="model_config.updated",
        object_type="model_config",
        object_id=str(new_config.id),
        details={
            "provider": new_config.provider,
            "model": new_config.model,
            "allow_data_sharing": new_config.allow_data_sharing,
            "has_endpoint": new_config.endpoint_url is not None,
            "has_credential": new_config.credential_ciphertext is not None,
        },
    )

    await session.commit()
    await session.refresh(new_config)
    return ModelConfigOut.model_validate(new_config)
