import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { IconMailPlus } from "@tabler/icons-react";
import { usePermission } from "../../../auth/permissions";
import type { UserInvite } from "../../../api/schema";
import { Button } from "../../../shared/ui/Button";
import { Input } from "../../../shared/ui/Input";
import { Modal } from "../../../shared/ui/Modal";
import { Select } from "../../../shared/ui/Select";
import { useToast } from "../../../shared/ui/Toast";
import {
  MSG_CANCEL,
  MSG_INVITE_FAILED,
  MSG_INVITE_SENT,
  MSG_INVITE_USER,
  MSG_ROLE,
  MSG_WORK_EMAIL,
} from "../../../shared/constants/messages";
import { mapUsersError, useInviteUser } from "../api";
import { ROLE_OPTIONS, inviteSchema, type InviteFormValues } from "../schemas";

const PLACEHOLDER_ROLE = "data_engineer";

export interface InviteUserModalProps {
  isOpen: boolean;
  onClose: () => void;
  onInvited?: (invite: UserInvite) => void;
}

/**
 * S8 invite modal (PRD Section 7, wireframe 1k).
 * Rendered only for roles holding `users.invite`; everyone else sees no invite
 * affordance at all (hidden, not disabled — PRD Section 2 RBAC rule).
 */
export function InviteUserModal({ isOpen, onClose, onInvited }: InviteUserModalProps) {
  const canInvite = usePermission("users.invite");
  const toast = useToast();
  const inviteMutation = useInviteUser();

  const [formError, setFormError] = useState<string | null>(null);
  const [emailError, setEmailError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    setFocus,
    formState: { errors },
  } = useForm<InviteFormValues>({
    resolver: zodResolver(inviteSchema),
    defaultValues: { email: "", role: PLACEHOLDER_ROLE },
  });

  // Reset on open so a previous attempt never leaks into the next invite.
  // `inviteMutation.error` is never rendered — errors are held in the local
  // state below — so the mutation itself needs no reset here.
  useEffect(() => {
    if (!isOpen) return;
    setFormError(null);
    setEmailError(null);
    reset({ email: "", role: PLACEHOLDER_ROLE });
  }, [isOpen, reset]);

  if (!canInvite) {
    return null;
  }

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    setEmailError(null);

    try {
      const invite = await inviteMutation.mutateAsync({
        email: values.email.trim(),
        role: values.role,
      });
      toast.success(MSG_INVITE_SENT);
      onInvited?.(invite);
      onClose();
    } catch (error) {
      // A duplicate account is the one failure that belongs on a field; every
      // other failure is reported as a form-level error.
      const mapped = mapUsersError(error, "form");
      if (mapped.field === "email") {
        setEmailError(mapped.message);
        setFocus("email");
      } else {
        setFormError(mapped.message || MSG_INVITE_FAILED);
      }
    }
  });

  const isPending = inviteMutation.isPending;

  return (
    <Modal
      isOpen={isOpen}
      onClose={isPending ? () => undefined : onClose}
      title={MSG_INVITE_USER}
      closeOnOverlayClick={!isPending}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isPending}>
            {MSG_CANCEL}
          </Button>
          <Button
            onClick={onSubmit}
            loading={isPending}
            leftIcon={<IconMailPlus className="h-4 w-4" aria-hidden="true" />}
          >
            {MSG_INVITE_USER}
          </Button>
        </>
      }
    >
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        {formError && (
          <div
            role="alert"
            className="rounded-md border border-[#f5c6cb] bg-[#f8d7da] px-3 py-2 text-sm text-[#721c24] dark:border-[#662025] dark:bg-[#3d1a1c] dark:text-[#f5a3a9]"
          >
            {formError}
          </div>
        )}

        <Input
          label={MSG_WORK_EMAIL}
          type="email"
          required
          autoComplete="off"
          spellCheck={false}
          disabled={isPending}
          error={errors.email?.message ?? emailError}
          {...register("email")}
        />

        <Select
          label={MSG_ROLE}
          required
          disabled={isPending}
          error={errors.role?.message}
          options={ROLE_OPTIONS}
          {...register("role")}
        />

        {/* Lets Enter inside a field submit the form; the visible action lives
            in the modal footer. */}
        <button type="submit" className="sr-only" tabIndex={-1}>
          {MSG_INVITE_USER}
        </button>
      </form>
    </Modal>
  );
}

export default InviteUserModal;
