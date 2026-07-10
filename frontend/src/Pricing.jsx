const TIERS = [
  {
    name: 'Free',
    price: '$0',
    period: 'forever',
    highlight: false,
    cta: { label: 'Get a key', href: '#/dashboard' },
    features: [
      '1,000 requests / month',
      '60 requests / minute',
      'All endpoints: search, contents, find-similar, list-domain, answer',
      'MCP server access',
      'Authenticity scores on every result',
    ],
  },
  {
    name: 'Pro',
    price: '$29',
    period: '/ month · coming soon',
    highlight: true,
    cta: { label: 'Join the waitlist', href: 'mailto:kanaparthiprembabu@gmail.com?subject=Cryo%20Pro%20waitlist' },
    features: [
      '50,000 requests / month',
      '300 requests / minute',
      'Priority answer generation',
      'Higher list-domain limits',
      'Email support',
    ],
  },
  {
    name: 'Scale',
    price: 'Custom',
    period: 'datasets & licensing',
    highlight: false,
    cta: { label: 'Contact us', href: 'mailto:kanaparthiprembabu@gmail.com?subject=Cryo%20Scale' },
    features: [
      'Bulk dataset exports (JSONL)',
      'Verified pre-AI training corpora',
      'Custom vertical ingestion',
      'Scoring methodology audits',
      'Volume API pricing',
    ],
  },
]

/**
 * Pricing — free beta today, honest "coming soon" on paid tiers.
 */
export default function Pricing() {
  return (
    <div className="w-full max-w-4xl pb-16">
      <h1 className="gradient-heading text-3xl mb-2">Pricing</h1>
      <p className="text-sm text-white/50 mb-10 font-light">
        Free while in beta. Paid tiers land when you need them — usage is already metered
        per key, so upgrading later is seamless.
      </p>

      <div className="grid md:grid-cols-3 gap-4">
        {TIERS.map((tier) => (
          <div
            key={tier.name}
            className={`liquid-glass rounded-xl p-6 flex flex-col ${
              tier.highlight ? 'ring-1 ring-[#4a9eff]/30' : ''
            }`}
          >
            <div className="text-sm text-white/60 mb-1">{tier.name}</div>
            <div className="flex items-baseline gap-2 mb-6">
              <span className="gradient-heading text-3xl">{tier.price}</span>
              <span className="text-[11px] text-white/30 font-light">{tier.period}</span>
            </div>
            <ul className="space-y-2.5 flex-1 mb-6">
              {tier.features.map((f) => (
                <li key={f} className="text-xs text-white/50 font-light flex gap-2">
                  <span className="text-[#4a9eff]/60 shrink-0">·</span>
                  {f}
                </li>
              ))}
            </ul>
            <a
              href={tier.cta.href}
              className={`text-center text-sm rounded-full px-5 py-2.5 transition-colors ${
                tier.highlight
                  ? 'bg-[#4a9eff]/15 text-[#7bb8ff] hover:bg-[#4a9eff]/25'
                  : 'liquid-glass text-white/60 hover:text-white'
              }`}
            >
              {tier.cta.label}
            </a>
          </div>
        ))}
      </div>

      <p className="text-[11px] text-white/20 mt-8 font-light">
        Answer requests count as 3 quota units; each retrieved page in /v1/contents counts as 1.
      </p>
    </div>
  )
}
