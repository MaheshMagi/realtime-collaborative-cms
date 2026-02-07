import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Link, useNavigate } from 'react-router-dom';
import { login, ApiError } from '../lib/api';
import { useAuth } from '../lib/auth';

interface LoginForm {
  email: string;
  password: string;
}

export default function Login() {
  const { register, handleSubmit, formState: { errors } } = useForm<LoginForm>();
  const [error, setError] = useState('');
  const { setToken } = useAuth();
  const navigate = useNavigate();

  const onSubmit = async (data: LoginForm) => {
    setError('');
    try {
      const { access_token } = await login(data.email, data.password);
      setToken(access_token);
      navigate('/');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Login failed');
    }
  };

  return (
    <div className="auth-page">
      <h1>Login</h1>
      {error && <p className="error">{error}</p>}
      <form onSubmit={handleSubmit(onSubmit)}>
        <input
          type="email"
          placeholder="Email"
          {...register('email', { required: 'Email is required' })}
        />
        {errors.email && <span className="field-error">{errors.email.message}</span>}

        <input
          type="password"
          placeholder="Password"
          {...register('password', { required: 'Password is required' })}
        />
        {errors.password && <span className="field-error">{errors.password.message}</span>}

        <button type="submit">Login</button>
      </form>
      <p>
        Don't have an account? <Link to="/register">Register</Link>
      </p>
    </div>
  );
}
