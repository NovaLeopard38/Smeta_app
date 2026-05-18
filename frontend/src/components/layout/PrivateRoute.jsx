import { Navigate } from 'react-router-dom';
import { useAuthContext } from '../../context/AuthContext';

export function PrivateRoute({ children, requireAdmin = false }) {
  const { currentUser, authToken } = useAuthContext();
  if (!authToken) return <Navigate to="/smetas" replace />;
  if (requireAdmin && !currentUser?.is_admin) return <Navigate to="/smetas" replace />;
  return children;
}
