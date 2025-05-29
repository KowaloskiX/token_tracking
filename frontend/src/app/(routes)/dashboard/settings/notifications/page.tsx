import { Separator } from "@/components/ui/separator";
import { NotificationsForm } from "@/components/dashboard/settings/forms/NotificationsForm";


export default function SettingsNotificationsPage() {
  return (
    <div className="h-[calc(100vh-128px)] overflow-y-auto scrollbar-hide space-y-6">
      <div>
        <h3 className="text-lg font-medium">Notifications</h3>
        <p className="text-sm text-muted-foreground">
          Configure how you receive notifications.
        </p>
      </div>
      <Separator />
      <NotificationsForm />
    </div>
  )
}