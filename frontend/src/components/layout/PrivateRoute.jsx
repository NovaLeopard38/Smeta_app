import { Navigate } from 'react-router-dom';
import { useAuthContext } from '../../context/AuthContext';

export function PrivateRoute({ children, requireAdmin = false }) {
  const { currentUser, authToken } = useAuthContext();
  if (!authToken) return <Navigate to="/smetas" replace />;
  // While user data is loading (token exists but user object not yet fetched),
  // render nothing to avoid premature redirect
  if (requireAdmin && !currentUser) return null;
  if (requireAdmin && !currentUser?.is_admin) return <Navigate to="/smetas" replace />;
  return children;
}
