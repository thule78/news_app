import 'package:flutter/material.dart';
import 'package:flutter_screenutil/flutter_screenutil.dart';

import 'app_scope.dart';
import 'core/constants/app_constants.dart';
import 'core/theme/app_theme.dart';
import 'screens/splash/splash_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const NewsAppRoot());
}

class NewsAppRoot extends StatefulWidget {
  const NewsAppRoot({super.key});

  @override
  State<NewsAppRoot> createState() => _NewsAppRootState();
}

class _NewsAppRootState extends State<NewsAppRoot> {
  late final AppControllers _controllers;

  @override
  void initState() {
    super.initState();
    _controllers = AppControllers();
  }

  @override
  void dispose() {
    _controllers.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AppScope(
      controllers: _controllers,
      child: ScreenUtilInit(
        designSize: const Size(390, 844),
        minTextAdapt: true,
        splitScreenMode: true,
        builder: (context, child) => AnimatedBuilder(
          animation: _controllers.themeProvider,
          builder: (context, _) {
            final fontScale = _controllers.themeProvider.fontScale;
            return MaterialApp(
              debugShowCheckedModeBanner: false,
              title: AppConstants.appName,
              themeMode: _controllers.themeProvider.themeMode,
              theme: AppTheme.light(fontScale),
              darkTheme: AppTheme.dark(fontScale),
              home: child,
            );
          },
        ),
        child: const SplashScreen(),
      ),
    );
  }
}
