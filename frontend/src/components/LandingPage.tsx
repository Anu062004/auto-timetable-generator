import '../landing.css'

interface Props {
  onEnter: () => void
}

export default function LandingPage({ onEnter }: Props) {
  return (
    <div className="landing-root">
      {/* Utility strip */}
      <div className="utility">
        <div className="utility-inner">
          <div className="utility-left">
            <span className="pin">▸ BMSITM · Bengaluru</span>
            <span className="dot">/</span>
            <span>Department of Artificial Intelligence &amp; Machine Learning</span>
          </div>
          <div className="utility-right">
            <a onClick={onEnter}>Faculty Portal</a>
            <span className="dot">·</span>
            <a onClick={onEnter}>Student Login</a>
            <span className="dot">·</span>
            <a onClick={onEnter}>Help</a>
          </div>
        </div>
      </div>

      {/* Masthead */}
      <header className="masthead">
        <div className="masthead-inner">
          <a className="brand" onClick={onEnter}>
            <img className="crest" src="/bmsitm-logo.png" alt="BMSITM crest" />
            <div className="brand-text">
              <div className="brand-title">BMS Institute of Technology &amp; Management</div>
              <div className="brand-sub">BMSITM · Estd. 2002 · Bengaluru</div>
            </div>
          </a>
          <div className="brand-rule"></div>
          <nav className="mast-nav">
            <a className="active" onClick={onEnter}>Generator</a>
            <a onClick={onEnter}>Sections</a>
            <a onClick={onEnter}>Courses</a>
            <a onClick={onEnter}>Faculty</a>
            <a onClick={onEnter}>Documentation</a>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="hero">
        <div className="hero-inner">
          <img
            className="hero-logo"
            src="/bmsitm-logo-transparent.png"
            alt="BMSITM crest"
          />
          <h1 className="hero-institute">
            BMS Institute of Technology <em>&amp;</em> Management
          </h1>
          <div className="hero-product">Automated Timetable Generator</div>
          <div className="hero-rule"></div>
          <button className="btn btn-primary hero-cta" onClick={onEnter}>
            <span>Generate Timetable</span>
            <span className="arrow"></span>
          </button>
        </div>
      </section>

      {/* Ledger strip */}
      <section className="ledger">
        <div className="ledger-inner">
          <div className="ledger-label">
            Solver guarantees, audited every run.
          </div>
          <div className="ledger-item">
            <div className="ledger-num">12<sup>+</sup></div>
            <div className="ledger-cap">Hard constraints H1–H12</div>
          </div>
          <div className="ledger-item">
            <div className="ledger-num">6</div>
            <div className="ledger-cap">Sections solved in parallel</div>
          </div>
          <div className="ledger-item">
            <div className="ledger-num">~20<sup>s</sup></div>
            <div className="ledger-cap">CP-SAT to feasible schedule</div>
          </div>
          <div className="ledger-item">
            <div className="ledger-num">0</div>
            <div className="ledger-cap">Clashes after verifier pass</div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer>
        <div className="foot-inner">
          <div className="foot-brand">
            <img src="/bmsitm-logo.png" alt="BMSITM" />
            <div>
              <div className="ft-name">
                BMS Institute of Technology<br />&amp; Management
              </div>
              <div className="ft-motto">
                Na hi jñānena sadṛśaṃ — Nothing is equal to knowledge.
              </div>
            </div>
          </div>
          <div className="foot-col">
            <h4>The Generator</h4>
            <ul>
              <li><a onClick={onEnter}>Open application</a></li>
              <li><a onClick={onEnter}>Sample schedules</a></li>
              <li><a onClick={onEnter}>Release notes</a></li>
            </ul>
          </div>
          <div className="foot-col">
            <h4>Department</h4>
            <ul>
              <li><a onClick={onEnter}>AI &amp; Machine Learning</a></li>
              <li><a onClick={onEnter}>Faculty roster</a></li>
              <li><a onClick={onEnter}>Course catalogue</a></li>
            </ul>
          </div>
          <div className="foot-col">
            <h4>Institute</h4>
            <ul>
              <li>Avalahalli, Doddaballapur Main Rd.</li>
              <li>Bengaluru 560 064</li>
              <li><a onClick={onEnter}>Contact registrar</a></li>
            </ul>
          </div>
        </div>
        <div className="foot-rule">
          <span>© BMSITM · Department of AI &amp; ML</span>
          <span>Build 2026.05 · Internal scheduling tool</span>
        </div>
      </footer>
    </div>
  )
}
