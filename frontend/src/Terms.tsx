import { Link } from "./router";
import SiteHeader from "./SiteHeader";

const sections: Array<[string, string[]]> = [
  ["1. About the service", [
    "Satya-Lekha reads documents you upload from a company's annual filing and compares them with the Companies Act, 2013 and related rules, and with each other. It produces findings, a control score and a report.",
    "By creating an account or using the service you agree to these terms.",
  ]],
  ["2. Not professional advice", [
    "Findings are pointers for a reviewer, not opinions. A passing result means documents are consistent with each other, not that they are correct or compliant.",
    "The legal references come from the authors' reading of the law and have not been reviewed by a qualified professional. The service does not replace a chartered accountant, company secretary, auditor or lawyer, and you remain responsible for your filings.",
  ]],
  ["3. Your account", [
    "You give us your full name, organization name, email address and a password. Provide accurate details and keep your password private. You are responsible for activity under your account.",
    "Register only if you are authorized to act for the organization you name.",
  ]],
  ["4. Your documents and reports", [
    "You confirm you have the right to upload the documents you submit. Documents are processed to produce a report.",
    "We keep the finished compliance report (document name, date, classification and findings) in your History so you can reopen it. We do not keep a copy of the file you upload for viewing.",
  ]],
  ["5. Acceptable use", [
    "Do not upload unlawful content, attempt to break or overload the service, probe other users' data, or use the service to mislead regulators or others.",
  ]],
  ["6. Accuracy and availability", [
    "Extraction from PDFs and scans can be wrong, especially for poor scans or unusual layouts. Check findings against the source documents before relying on them.",
    "The service is provided as is, without warranty, and may be unavailable from time to time.",
  ]],
  ["7. Liability", [
    "To the extent the law allows, we are not liable for losses arising from reliance on the service's output, including penalties, missed filings or incorrect filings.",
  ]],
  ["8. Changes and contact", [
    "We may update these terms. Continued use after a change means you accept it. Questions about these terms go to the administrator of your deployment of Satya-Lekha.",
  ]],
];

export default function Terms() {
  return (
    <div className="page">
      <SiteHeader />
      <main className="prose">
        <h1>Terms &amp; Conditions</h1>
        <p className="muted">Please read these before creating an account.</p>
        {sections.map(([title, paragraphs]) => (
          <section key={title}>
            <h2>{title}</h2>
            {paragraphs.map((p) => <p key={p}>{p}</p>)}
          </section>
        ))}
        <p><Link to="/register">Back to registration</Link></p>
      </main>
    </div>
  );
}
