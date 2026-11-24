import { useEffect, useRef } from 'react'
import Plotly from 'plotly.js-dist-min'

export default function Plot({ data, layout = {}, className = '' }) {
  const ref = useRef(null)
  useEffect(() => {
    if (!ref.current) return undefined
    Plotly.react(ref.current, data, { paper_bgcolor: 'transparent', plot_bgcolor: 'transparent', font: { color: '#9aa4b2', family: 'Inter, system-ui' }, margin: { l: 46, r: 18, t: 12, b: 42 }, ...layout }, { responsive: true, displayModeBar: false })
    return () => { if (ref.current) Plotly.purge(ref.current) }
  }, [data, layout])
  return <div ref={ref} className={`plot ${className}`} />
}
