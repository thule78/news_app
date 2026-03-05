import 'package:flutter/material.dart';

import '../models/article_model.dart';
import '../repositories/article_repository.dart';

class CategoryArticlesProvider extends ChangeNotifier {
  CategoryArticlesProvider(this._articleRepository);

  final ArticleRepository _articleRepository;

  final Map<int, List<ArticleModel>> _itemsByCategory =
      <int, List<ArticleModel>>{};
  final Map<int, int> _pageByCategory = <int, int>{};
  final Map<int, bool> _hasMoreByCategory = <int, bool>{};
  final Set<int> _loadingInitial = <int>{};
  final Set<int> _loadingMore = <int>{};
  final Map<int, String> _errors = <int, String>{};

  List<ArticleModel> items(int categoryId) =>
      _itemsByCategory[categoryId] ?? const <ArticleModel>[];
  bool isLoadingInitial(int categoryId) => _loadingInitial.contains(categoryId);
  bool isLoadingMore(int categoryId) => _loadingMore.contains(categoryId);
  bool hasMore(int categoryId) => _hasMoreByCategory[categoryId] ?? true;
  String? error(int categoryId) => _errors[categoryId];

  Future<void> fetchInitial(int categoryId) async {
    _loadingInitial.add(categoryId);
    _errors.remove(categoryId);
    _pageByCategory[categoryId] = 1;
    _hasMoreByCategory[categoryId] = true;
    notifyListeners();

    final result = await _articleRepository.fetchByCategory(
      categoryId: categoryId,
      page: 1,
    );
    if (result.isSuccess && result.data != null) {
      _itemsByCategory[categoryId] = result.data!;
      if (result.data!.isEmpty) {
        _hasMoreByCategory[categoryId] = false;
      }
    } else {
      _errors[categoryId] = result.error ?? 'Unable to load category articles.';
    }

    _loadingInitial.remove(categoryId);
    notifyListeners();
  }

  Future<void> fetchMore(int categoryId) async {
    if (_loadingMore.contains(categoryId) || !hasMore(categoryId)) return;

    _loadingMore.add(categoryId);
    _errors.remove(categoryId);
    notifyListeners();

    final nextPage = (_pageByCategory[categoryId] ?? 1) + 1;
    final result = await _articleRepository.fetchByCategory(
      categoryId: categoryId,
      page: nextPage,
    );
    if (result.isSuccess && result.data != null) {
      if (result.data!.isEmpty) {
        _hasMoreByCategory[categoryId] = false;
      } else {
        _pageByCategory[categoryId] = nextPage;
        final existing = items(categoryId);
        _itemsByCategory[categoryId] = <ArticleModel>[
          ...existing,
          ...result.data!,
        ];
      }
    } else {
      _errors[categoryId] = result.error ?? 'Unable to load more articles.';
    }

    _loadingMore.remove(categoryId);
    notifyListeners();
  }
}
