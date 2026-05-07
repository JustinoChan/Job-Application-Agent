import type { ReactNode } from "react";

export default function ConfirmDialog({
  open,
  title,
  children,
  onCancel,
  onConfirm
}: {
  open: boolean;
  title: string;
  children: ReactNode;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  if (!open) return null;
  return (
    <div className="modal-backdrop">
      <div className="modal">
        <h2>{title}</h2>
        <div>{children}</div>
        <div className="modal-actions">
          <button className="secondary" onClick={onCancel}>Cancel</button>
          <button onClick={onConfirm}>Confirm</button>
        </div>
      </div>
    </div>
  );
}
