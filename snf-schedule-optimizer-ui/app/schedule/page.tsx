import { redirect } from "next/navigation";

export default async function SchedulePage() {
  redirect("/?tab=scheduling&view=timeline");
}
