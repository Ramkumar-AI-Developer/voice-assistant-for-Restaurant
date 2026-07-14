import { NavLink, useNavigate } from 'react-router-dom';
import { useSelector, useDispatch } from 'react-redux';
import { logout } from '../store/authSlice';
import { HiOutlineHome, HiOutlineClipboardList, HiOutlinePhone, HiOutlineUserGroup, HiOutlineLogout } from 'react-icons/hi';
import { MdOutlineRestaurantMenu } from 'react-icons/md';

export default function Sidebar() {
  const user = useSelector((state) => state.auth.user);
  const dispatch = useDispatch();
  const navigate = useNavigate();

  const handleLogout = () => {
    dispatch(logout());
    navigate('/login');
  };

  const navItems = [
    { path: '/', icon: <HiOutlineHome />, label: 'Dashboard' },
    { path: '/menu', icon: <MdOutlineRestaurantMenu />, label: 'Menu' },
    { path: '/orders', icon: <HiOutlineClipboardList />, label: 'Orders' },
    { path: '/calls', icon: <HiOutlinePhone />, label: 'Call History' },
  ];

  if (user?.is_admin) {
    navItems.push({ path: '/users', icon: <HiOutlineUserGroup />, label: 'Users' });
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <img src="/favicon.png" alt="Vasantha Vilas" className="sidebar-logo-img" style={{ width: '40px', height: '40px', borderRadius: '8px' }} />
          <div>
            <h1>Vasantha Vilas</h1>
            <p>AI Voice Dashboard</p>
          </div>
        </div>
      </div>

      <nav className="sidebar-nav">
        <div className="nav-section-title">Main Menu</div>
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === '/'}
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
          >
            {item.icon}
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="sidebar-user">
          <div className="user-avatar">
            {user?.username?.[0]?.toUpperCase() || 'U'}
          </div>
          <div className="user-info">
            <h4>{user?.username || 'User'}</h4>
            <p>{user?.is_admin ? 'Admin' : 'Staff'}</p>
          </div>
        </div>
        <button className="logout-btn" onClick={handleLogout}>
          <HiOutlineLogout /> Sign out
        </button>
      </div>
    </aside>
  );
}
