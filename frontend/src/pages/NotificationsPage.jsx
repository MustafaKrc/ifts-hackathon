import React from "react";
import { useOutletContext } from "react-router-dom";

import NotificationCenter from "../components/NotificationCenter";

export default function NotificationsPage() {
  const ctx = useOutletContext();
  return (
    <NotificationCenter
      notifications={ctx.notifications}
      onMarkRead={ctx.handleMarkRead}
    />
  );
}
