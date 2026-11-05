import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <div className="p-6">
      <p className="mb-2">Page not found.</p>
      <Link to="/" className="text-sm underline">
        Back to questions
      </Link>
    </div>
  )
}
