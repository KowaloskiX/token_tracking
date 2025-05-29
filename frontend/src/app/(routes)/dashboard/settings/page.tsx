import { ProfileForm } from "@/components/dashboard/settings/forms/ProfileForm";


export default function SettingsProfilePage() {
  return (
    <div className="h-[calc(100vh-128px)] overflow-y-auto scrollbar-hide">
      <ProfileForm />
    </div>
  )
}