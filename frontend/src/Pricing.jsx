/**
 * Pricing — one honest free allocation. Billing is not live; over-quota is a
 * visible hard stop, never a silent degradation. Numbers match what the
 * backend actually enforces (1,000 req/mo, 60/min per key).
 */
export default function Pricing() {
  return (
    <>
      <section className="page-intro pricing-intro">
        <p className="eyebrow"><span></span> PRICING / BOUNDARIES FIRST</p>
        <h1>Clear limits.<br />No <em>mystery meter.</em></h1>
        <p>
          CRYO starts with one honest free allocation. Billing is not live yet; exceeding quota
          means a visible hard stop with a reset date, not a silent degradation.
        </p>
      </section>

      <section className="quota-sheet">
        <div className="quota-main">
          <p>FREE / DEVELOPER</p>
          <strong>1,000</strong>
          <span>requests / month</span>
          <hr />
          <div>
            <p>60 / minute</p>
            <p>Resets on the first day of your monthly period.</p>
          </div>
          <a className="ink-button" href="#/dashboard">Get API key <span aria-hidden="true">→</span></a>
        </div>
        <div className="quota-terms">
          <p className="eyebrow"><span></span> HOW CALLS COUNT</p>
          <dl>
            <div><dt>Search / Contents / List-domain</dt><dd>1 unit</dd></div>
            <div><dt>Find similar</dt><dd>3 units</dd></div>
            <div><dt>Grounded answer</dt><dd>3 units</dd></div>
            <div><dt>Usage read</dt><dd>0 units</dd></div>
            <div><dt>Over the limit today</dt><dd>Hard stop + reset date</dd></div>
          </dl>
          <p className="warning">
            <b>NOT LIVE YET</b>
            Paid plans and checkout are intentionally out of scope. Need more volume? Contact us
            and state your workload — usage is already metered per key, so upgrading later is
            seamless.
          </p>
        </div>
      </section>

      <section className="price-faq">
        <p className="eyebrow"><span></span> THE HONEST VERSION</p>
        <div>
          <h2>What happens<br />when I run out?</h2>
          <p>
            The API returns a specific quota response with the reset date. The website repeats
            that information and links back here, and never implies that a paid upgrade will work
            until billing actually exists.
          </p>
        </div>
        <a href="mailto:kanaparthiprembabu@gmail.com?subject=Cryo%20volume">
          Contact about volume <span aria-hidden="true">↗</span>
        </a>
      </section>
    </>
  )
}
