import {
  ApartmentOutlined,
  AuditOutlined,
  FilePdfOutlined,
  FileSearchOutlined,
  HistoryOutlined,
  ReadOutlined,
} from "@ant-design/icons";
import { Button } from "antd";
import { useAuth } from "./auth";
import { Link, navigate } from "./router";
import SiteHeader from "./SiteHeader";

const features = [
  {
    icon: <FileSearchOutlined />,
    title: "Reads the whole filing",
    text: "Upload financial statements, the Directors' Report, the Auditor's Report, an AGM notice or invoices. Each document is read and labelled automatically.",
  },
  {
    icon: <AuditOutlined />,
    title: "Rules, not guesses",
    text: "Every check is a fixed rule under the Companies Act, 2013 and related rules. A finding quotes the exact text or figures it relied on.",
  },
  {
    icon: <ApartmentOutlined />,
    title: "Cross-document checks",
    text: "Does the cash flow statement tie to the balance sheet? Does the Directors' Report agree with the accounts? Upload several documents and we compare them.",
  },
  {
    icon: <ReadOutlined />,
    title: "Regulatory evidence",
    text: "Findings can point to the regulation passages they relate to, with their source and effective dates, so a reviewer can verify the basis.",
  },
  {
    icon: <FilePdfOutlined />,
    title: "A report you can hand over",
    text: "Get a control score and a printable PDF report that lists every finding and its evidence.",
  },
  {
    icon: <HistoryOutlined />,
    title: "History of past reports",
    text: "Each finished report is saved to your account. Reopen it any time. Your original uploaded file is never stored.",
  },
];

const steps = [
  ["1", "Create an account", "Sign up with your organization and work email."],
  ["2", "Upload a document", "A PDF from your annual filing, up to 20 MB."],
  ["3", "Review the findings", "Open each finding to see the evidence behind it."],
];

export default function Home() {
  const { user } = useAuth();
  const start = () => navigate(user ? "/app" : "/register");

  return (
    <div className="page">
      <SiteHeader />
      <main>
        <section className="hero">
          <p className="eyebrow">Annual filing checks for Indian companies</p>
          <h1>Find the inconsistencies in your filing before a reviewer does.</h1>
          <p className="hero-sub">
            Satya-Lekha checks your financial statements and reports against the Companies Act, 2013, and shows the
            evidence for every finding.
          </p>
          <div className="hero-actions">
            <Button type="primary" size="large" onClick={start}>{user ? "Check a document" : "Create a free account"}</Button>
            {!user && <Button size="large" onClick={() => navigate("/login")}>Sign in</Button>}
          </div>
        </section>

        <section className="section" aria-labelledby="features-title">
          <h2 id="features-title">What it does</h2>
          <div className="feature-grid">
            {features.map((f) => (
              <article key={f.title} className="feature-card">
                <div className="feature-icon" aria-hidden="true">{f.icon}</div>
                <h3>{f.title}</h3>
                <p>{f.text}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="section" aria-labelledby="how-title">
          <h2 id="how-title">How it works</h2>
          <ol className="steps">
            {steps.map(([n, title, text]) => (
              <li key={n}><span className="step-n">{n}</span><div><h3>{title}</h3><p>{text}</p></div></li>
            ))}
          </ol>
        </section>

        <section className="section notice">
          <p>
            <b>A finding is a pointer for a reviewer, not an opinion.</b> A passing result means the documents are
            consistent with each other, not that they are right. Read our <Link to="/terms">Terms &amp; Conditions</Link>.
          </p>
        </section>
      </main>
      <footer className="site-footer">
        <span>© Satya-Lekha</span>
        <Link to="/terms">Terms &amp; Conditions</Link>
      </footer>
    </div>
  );
}
