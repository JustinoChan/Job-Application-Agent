export default function ResumePreview({ html, src }: { html?: string; src?: string }) {
  if (src) {
    return <iframe className="resume-frame" src={src} sandbox="allow-same-origin" title="Resume preview" />;
  }
  return (
    <iframe
      className="resume-frame"
      srcDoc={html || "<p>No resume preview available.</p>"}
      sandbox=""
      title="Resume preview"
    />
  );
}
