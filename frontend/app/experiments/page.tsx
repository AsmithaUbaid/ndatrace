import { redirect } from "next/navigation";

/** Preserve historical links while keeping /project as the single presentation source. */
export default function ExperimentsPage() {
  redirect("/project");
}
