/**
 * Legal — Privacy Policy and Terms of Service, written to reflect what Cryo
 * actually does. mode: 'privacy' | 'terms'.
 */

const CONTACT = 'kanaparthiprembabu@gmail.com'
const UPDATED = 'Last updated 14 July 2026'

export default function Legal({ mode }) {
  return mode === 'terms' ? <Terms /> : <Privacy />
}

function Privacy() {
  return (
    <section className="legal-doc">
      <p className="eyebrow"><span></span> CRYO / PRIVACY</p>
      <h1>Privacy<br /><em>policy.</em></h1>
      <p className="updated">{UPDATED}</p>

      <p className="lead">
        Cryo is a search API over a frozen, pre-2022 web archive. This policy explains what
        personal data we collect when you use the service, why, and who we share it with. We
        keep it minimal on purpose.
      </p>

      <h2>What we collect</h2>
      <ul>
        <li><strong>Account details</strong> — your email address (and name, if provided) when you sign up. Authentication is handled by our provider, Clerk.</li>
        <li><strong>API keys</strong> — we store only a one-way hash of each key, never the key itself.</li>
        <li><strong>Usage data</strong> — per-key request counts, endpoints called, and timestamps, used to meter quotas and prevent abuse.</li>
        <li><strong>Search queries</strong> — processed to return results and may be logged transiently for operating the service, debugging, and abuse prevention.</li>
        <li><strong>Basic technical data</strong> — IP address and request metadata, as is standard for any web service, used for security and rate limiting.</li>
      </ul>

      <h2>What we don't collect</h2>
      <p>We don't sell your personal data. We don't build advertising profiles. We don't track you across other sites.</p>

      <h2>Service providers</h2>
      <p>We rely on a small number of processors to run Cryo:</p>
      <ul>
        <li><strong>Clerk</strong> — authentication and account management.</li>
        <li><strong>Vercel</strong> — hosting for the website.</li>
        <li><strong>IONOS</strong> — hosting for the API and database.</li>
      </ul>
      <p>
        The searchable corpus itself consists of publicly available, pre-2022 web content
        archived from sources such as the Internet Archive (Wayback Machine), Wikipedia, and
        public web crawls. That content is not personal data you provided to us.
      </p>

      <h2>Cookies</h2>
      <p>Cryo uses only the cookies its authentication provider sets to keep you signed in. We do not use advertising or analytics cookies at this time.</p>

      <h2>Data retention</h2>
      <p>Account data is kept while your account is active. Usage records are retained for metering and audit purposes. You can request deletion of your account and associated data at any time.</p>

      <h2>Your rights</h2>
      <p>You can request access to, correction of, or deletion of your personal data by emailing us at <a href={`mailto:${CONTACT}`}>{CONTACT}</a>. Depending on your location, you may have additional rights under laws such as the GDPR or CCPA.</p>

      <h2>Security</h2>
      <p>All traffic is served over HTTPS. API keys are stored hashed. We restrict network access to the services that need it. No system is perfectly secure, but we take reasonable measures to protect your data.</p>

      <h2>Children</h2>
      <p>Cryo is a developer tool and is not directed at children under 13 (or the minimum age in your jurisdiction). We do not knowingly collect their data.</p>

      <h2>Changes</h2>
      <p>We may update this policy as the product evolves. Material changes will be reflected by the "last updated" date above.</p>

      <h2>Contact</h2>
      <p>Questions about privacy? Email <a href={`mailto:${CONTACT}`}>{CONTACT}</a>.</p>
    </section>
  )
}

function Terms() {
  return (
    <section className="legal-doc">
      <p className="eyebrow"><span></span> CRYO / TERMS</p>
      <h1>Terms of<br /><em>service.</em></h1>
      <p className="updated">{UPDATED}</p>

      <p className="lead">
        These terms govern your use of Cryo — a search API over a frozen, pre-2022 web archive,
        currently offered as a free beta. By creating an account or using the service, you agree
        to them.
      </p>

      <h2>The service</h2>
      <p>Cryo provides search, retrieval, and grounded-answer access to a corpus of publicly available web content captured before 2022, via a website, REST API, SDK, and MCP server. The service is in beta and provided free of charge; features, limits, and availability may change.</p>

      <h2>Accounts and API keys</h2>
      <ul>
        <li>You are responsible for keeping your API keys secret and for all activity that occurs under them.</li>
        <li>If a key is exposed, revoke it in your dashboard immediately — revocation takes effect right away.</li>
        <li>Provide accurate account information and keep it current.</li>
      </ul>

      <h2>Acceptable use</h2>
      <p>You agree not to:</p>
      <ul>
        <li>Use Cryo for unlawful purposes or to infringe others' rights.</li>
        <li>Exceed, evade, or attempt to circumvent rate limits or quotas.</li>
        <li>Attempt to disrupt, overload, reverse-engineer, or gain unauthorized access to the service.</li>
        <li>Resell or redistribute the service or bulk corpus without our written permission.</li>
      </ul>

      <h2>Content and provenance</h2>
      <p>
        The corpus consists of third-party content archived from the public web. Cryo does not own
        this content and provides it on an "as is" basis. Authenticity scores and provenance
        signals are best-effort estimates, not guarantees. You are responsible for how you use
        retrieved content and for complying with the rights of the original sources.
      </p>

      <h2>Free beta</h2>
      <p>Cryo is currently free. There is no billing. Quotas and features may change, and we may introduce paid plans in the future. We may modify, suspend, or discontinue the service at any time.</p>

      <h2>Disclaimer of warranties</h2>
      <p>The service is provided "as is" and "as available," without warranties of any kind, express or implied, including accuracy, fitness for a particular purpose, or uninterrupted availability.</p>

      <h2>Limitation of liability</h2>
      <p>To the maximum extent permitted by law, Cryo and its operators will not be liable for any indirect, incidental, or consequential damages arising from your use of the service. As a free beta, the service is used at your own risk.</p>

      <h2>Termination</h2>
      <p>We may suspend or terminate access for violations of these terms or misuse of the service. You may stop using Cryo and request account deletion at any time.</p>

      <h2>Changes</h2>
      <p>We may update these terms as the product evolves; the "last updated" date above reflects the current version. Continued use after changes constitutes acceptance.</p>

      <h2>Contact</h2>
      <p>Questions about these terms? Email <a href={`mailto:${CONTACT}`}>{CONTACT}</a>.</p>
    </section>
  )
}
