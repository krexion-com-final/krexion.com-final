import { useEffect, useState } from "react";
import axios from "axios";
import { motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { MousePointerClick, TrendingUp, DollarSign, Users } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const COLORS = ['#4F7FFF', '#3D66D9', '#6B95FF', '#22C55E', '#F59E0B'];

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const token = localStorage.getItem("token");
      const response = await axios.get(`${API}/dashboard/stats`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setStats(response.data);
    } catch (error) {
      console.error("Error fetching stats:", error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-white">Loading dashboard...</div>
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-gray-400">No data available</div>
      </div>
    );
  }

  const statCards = [
    {
      title: "Total Clicks",
      value: (stats.total_clicks || 0).toLocaleString(),
      change: `+${stats.clicks_change || 0}% from last month`,
      changeColor: "#22C55E",
      icon: MousePointerClick,
      color: "#4F7FFF",
      testid: "stat-clicks"
    },
    {
      title: "Conversions",
      value: (stats.total_conversions || 0).toLocaleString(),
      change: `${stats.conversion_rate || 0}% conversion rate`,
      changeColor: "#22C55E",
      icon: TrendingUp,
      color: "#3D66D9",
      testid: "stat-conversions"
    },
    {
      title: "Active Users",
      value: (stats.active_users || 0).toLocaleString(),
      change: `+${stats.users_change || 0}% this week`,
      changeColor: "#22C55E",
      icon: Users,
      color: "#6B95FF",
      testid: "stat-users"
    },
    {
      title: "Revenue",
      value: `$${(stats.revenue || 0).toLocaleString()}`,
      change: `+$${(stats.revenue_change || 0).toLocaleString()} this month`,
      changeColor: "#22C55E",
      icon: DollarSign,
      color: "#22C55E",
      testid: "stat-revenue"
    },
  ];

  const deviceData = (stats.clicks_by_device || []).map(item => ({
    name: item.device.charAt(0).toUpperCase() + item.device.slice(1),
    value: item.count
  }));

  return (
    <motion.div 
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3 }}
      className="space-y-6" 
      data-testid="dashboard"
    >
      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((stat, index) => {
          const Icon = stat.icon;
          return (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1, duration: 0.4 }}
              whileHover={{ scale: 1.05, y: -5 }}
            >
              <Card 
                className="transition-all duration-300 cursor-pointer"
                style={{ 
                  background: 'rgba(0, 0, 0, 0.4)',
                  backdropFilter: 'blur(12px)',
                  border: '1px solid rgba(79, 127, 255, 0.3)',
                  boxShadow: '0 4px 20px rgba(0, 0, 0, 0.5)'
                }}
                data-testid={stat.testid}
              >
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-sm font-medium text-gray-300">
                    {stat.title}
                  </CardTitle>
                  <motion.div
                    whileHover={{ scale: 1.2, rotate: 5 }}
                    className="w-10 h-10 rounded-lg flex items-center justify-center"
                    style={{ 
                      background: `linear-gradient(135deg, ${stat.color}30, ${stat.color}10)`,
                      border: `1px solid ${stat.color}40`
                    }}
                  >
                    <Icon size={20} style={{ color: stat.color }} />
                  </motion.div>
                </CardHeader>
                <CardContent>
                  <div className="text-3xl font-bold text-white mb-1">{stat.value}</div>
                  <p className="text-xs" style={{ color: stat.changeColor }}>
                    {stat.change}
                  </p>
                </CardContent>
              </Card>
            </motion.div>
          );
        })}
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Clicks Chart */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.5, duration: 0.4 }}
        >
          <Card 
            style={{ 
              background: 'rgba(0, 0, 0, 0.4)',
              backdropFilter: 'blur(12px)',
              border: '1px solid rgba(79, 127, 255, 0.2)',
            }}
            data-testid="clicks-chart"
          >
            <CardHeader>
              <CardTitle className="text-lg text-white">Clicks Over Time</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={stats.clicks_by_date || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(79, 127, 255, 0.1)" />
                  <XAxis dataKey="date" stroke="#6B7280" style={{ fontSize: 12 }} />
                  <YAxis stroke="#6B7280" style={{ fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'rgba(0, 0, 0, 0.9)',
                      border: '1px solid rgba(79, 127, 255, 0.3)',
                      borderRadius: '8px',
                      color: '#FFFFFF'
                    }}
                  />
                  <Line 
                    type="monotone" 
                    dataKey="count" 
                    stroke="#4F7FFF" 
                    strokeWidth={3} 
                    dot={{ fill: '#4F7FFF', r: 4 }}
                    activeDot={{ r: 6 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </motion.div>

        {/* Revenue Chart */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.6, duration: 0.4 }}
        >
          <Card 
            style={{ 
              background: 'rgba(0, 0, 0, 0.4)',
              backdropFilter: 'blur(12px)',
              border: '1px solid rgba(79, 127, 255, 0.2)',
            }}
            data-testid="revenue-chart"
          >
            <CardHeader>
              <CardTitle className="text-lg text-white">Revenue Over Time</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={stats.revenue_by_date || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(79, 127, 255, 0.1)" />
                  <XAxis dataKey="date" stroke="#6B7280" style={{ fontSize: 12 }} />
                  <YAxis stroke="#6B7280" style={{ fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'rgba(0, 0, 0, 0.9)',
                      border: '1px solid rgba(79, 127, 255, 0.3)',
                      borderRadius: '8px',
                      color: '#FFFFFF'
                    }}
                  />
                  <Line 
                    type="monotone" 
                    dataKey="revenue" 
                    stroke="#22C55E" 
                    strokeWidth={3} 
                    dot={{ fill: '#22C55E', r: 4 }}
                    activeDot={{ r: 6 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* Bottom Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Countries Chart */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.7, duration: 0.4 }}
        >
          <Card 
            style={{ 
              background: 'rgba(0, 0, 0, 0.4)',
              backdropFilter: 'blur(12px)',
              border: '1px solid rgba(79, 127, 255, 0.2)',
            }}
            data-testid="country-chart"
          >
            <CardHeader>
              <CardTitle className="text-lg text-white">Top Countries</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={stats.clicks_by_country || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(79, 127, 255, 0.1)" />
                  <XAxis dataKey="country" stroke="#6B7280" style={{ fontSize: 12 }} />
                  <YAxis stroke="#6B7280" style={{ fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'rgba(0, 0, 0, 0.9)',
                      border: '1px solid rgba(79, 127, 255, 0.3)',
                      borderRadius: '8px',
                      color: '#FFFFFF'
                    }}
                  />
                  <Bar dataKey="count" fill="#4F7FFF" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </motion.div>

        {/* Device Chart */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.8, duration: 0.4 }}
        >
          <Card 
            style={{ 
              background: 'rgba(0, 0, 0, 0.4)',
              backdropFilter: 'blur(12px)',
              border: '1px solid rgba(79, 127, 255, 0.2)',
            }}
            data-testid="device-chart"
          >
            <CardHeader>
              <CardTitle className="text-lg text-white">Device Breakdown</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={deviceData}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                    outerRadius={100}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    {deviceData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'rgba(0, 0, 0, 0.9)',
                      border: '1px solid rgba(79, 127, 255, 0.3)',
                      borderRadius: '8px',
                      color: '#FFFFFF'
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </motion.div>
  );
}
