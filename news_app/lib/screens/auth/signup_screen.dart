import 'package:flutter/material.dart';
import 'package:flutter_screenutil/flutter_screenutil.dart';

import '../../app_scope.dart';
import '../home/home_screen.dart';

class SignupScreen extends StatefulWidget {
  const SignupScreen({super.key});

  @override
  State<SignupScreen> createState() => _SignupScreenState();
}

class _SignupScreenState extends State<SignupScreen> {
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final auth = AppScope.of(context).authProvider;
    final ok = await auth.signup(
      _emailController.text,
      _passwordController.text,
    );
    if (!mounted || !ok) return;
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => const HomeScreen()),
      (_) => false,
    );
  }

  @override
  Widget build(BuildContext context) {
    final auth = AppScope.of(context).authProvider;
    return Scaffold(
      appBar: AppBar(title: const Text('Signup')),
      body: AnimatedBuilder(
        animation: auth,
        builder: (context, _) {
          return Padding(
            padding: EdgeInsets.all(16.w),
            child: Column(
              children: [
                TextField(
                  controller: _emailController,
                  decoration: const InputDecoration(labelText: 'Email'),
                ),
                SizedBox(height: 12.h),
                TextField(
                  controller: _passwordController,
                  decoration: const InputDecoration(labelText: 'Password'),
                  obscureText: true,
                ),
                SizedBox(height: 16.h),
                FilledButton(
                  onPressed: auth.isSubmitting ? null : _submit,
                  child: Text(
                    auth.isSubmitting ? 'Loading...' : 'Create account',
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}
