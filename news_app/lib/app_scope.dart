import 'package:flutter/material.dart';

import 'core/theme/theme_provider.dart';
import 'providers/article_detail_provider.dart';
import 'providers/auth_provider.dart';
import 'providers/category_articles_provider.dart';
import 'providers/home_categories_provider.dart';
import 'providers/popular_provider.dart';
import 'providers/profile_provider.dart';
import 'providers/search_provider.dart';
import 'providers/settings_provider.dart';
import 'repositories/article_repository.dart';
import 'repositories/auth_repository.dart';
import 'repositories/category_repository.dart';
import 'repositories/profile_repository.dart';
import 'repositories/settings_repository.dart';
import 'services/http_client.dart';

class AppControllers {
  AppControllers()
    : httpClient = AppHttpClient(),
      themeProvider = ThemeProvider(),
      settingsRepository = SettingsRepository(),
      authRepository = AuthRepository(),
      profileRepository = ProfileRepository() {
    categoryRepository = CategoryRepository(httpClient);
    articleRepository = ArticleRepository(httpClient);

    settingsProvider = SettingsProvider(settingsRepository, themeProvider);
    homeCategoriesProvider = HomeCategoriesProvider(
      categoryRepository,
      settingsProvider,
    );
    popularProvider = PopularProvider(articleRepository);
    categoryArticlesProvider = CategoryArticlesProvider(articleRepository);
    articleDetailProvider = ArticleDetailProvider(articleRepository);
    searchProvider = SearchProvider(articleRepository);
    profileProvider = ProfileProvider(profileRepository);
    authProvider = AuthProvider(authRepository, profileRepository);
  }

  final AppHttpClient httpClient;
  final ThemeProvider themeProvider;

  late final CategoryRepository categoryRepository;
  late final ArticleRepository articleRepository;
  final SettingsRepository settingsRepository;
  final AuthRepository authRepository;
  final ProfileRepository profileRepository;

  late final SettingsProvider settingsProvider;
  late final HomeCategoriesProvider homeCategoriesProvider;
  late final PopularProvider popularProvider;
  late final CategoryArticlesProvider categoryArticlesProvider;
  late final ArticleDetailProvider articleDetailProvider;
  late final SearchProvider searchProvider;
  late final ProfileProvider profileProvider;
  late final AuthProvider authProvider;

  void dispose() {
    homeCategoriesProvider.dispose();
    popularProvider.dispose();
    categoryArticlesProvider.dispose();
    articleDetailProvider.dispose();
    searchProvider.dispose();
    settingsProvider.dispose();
    profileProvider.dispose();
    authProvider.dispose();
    themeProvider.dispose();
    httpClient.dispose();
  }
}

class AppScope extends InheritedWidget {
  const AppScope({super.key, required this.controllers, required super.child});

  final AppControllers controllers;

  static AppControllers of(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<AppScope>();
    assert(scope != null, 'AppScope not found in widget tree.');
    return scope!.controllers;
  }

  @override
  bool updateShouldNotify(covariant AppScope oldWidget) =>
      oldWidget.controllers != controllers;
}
