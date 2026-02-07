import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Link, useNavigate } from 'react-router-dom';
import { register as registerUser, login, ApiError } from '../lib/api';
import { useAuth } from '../lib/auth';

interface RegisterForm {
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  password: string;
}

export default function Register() {
  const { register, handleSubmit, formState: { errors } } = useForm<RegisterForm>();
  const [error, setError] = useState('');
  const { setToken } = useAuth();
  const navigate = useNavigate();

  const onSubmit = async (data: RegisterForm) => {
    setError('');
    try {
      await registerUser(data);
      const { access_token } = await login(data.email, data.password);
      setToken(access_token);
      navigate('/');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Registration failed');
    }
  };

  return (
    <div className="auth-page">
      <h1>Register</h1>
      {error && <p className="error">{error}</p>}
      <form onSubmit={handleSubmit(onSubmit)}>
        <input
          placeholder="Username"
          {...register('username', { required: 'Username is required' })}
        />
        {errors.username && <span className="field-error">{errors.username.message}</span>}

        <input
          type="email"
          placeholder="Email"
          {...register('email', { required: 'Email is required' })}
        />
        {errors.email && <span className="field-error">{errors.email.message}</span>}

        <input
          placeholder="First name"
          {...register('first_name', { required: 'First name is required' })}
        />
        {errors.first_name && <span className="field-error">{errors.first_name.message}</span>}

        <input
          placeholder="Last name"
          {...register('last_name', { required: 'Last name is required' })}
        />
        {errors.last_name && <span className="field-error">{errors.last_name.message}</span>}

        <input
          type="password"
          placeholder="Password"
          {...register('password', { required: 'Password is required', minLength: { value: 6, message: 'At least 6 characters' } })}
        />
        {errors.password && <span className="field-error">{errors.password.message}</span>}

        <button type="submit">Register</button>
      </form>
      <p>
        Already have an account? <Link to="/login">Login</Link>
      </p>
    </div>
  );
}
