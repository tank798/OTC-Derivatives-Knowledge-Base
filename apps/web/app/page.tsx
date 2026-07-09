import { Workspace, WorkspaceErrorBoundary } from "../components/workspace";

export default function HomePage() {
  return (
    <WorkspaceErrorBoundary>
      <Workspace />
    </WorkspaceErrorBoundary>
  );
}
