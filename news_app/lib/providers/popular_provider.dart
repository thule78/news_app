import 'package:flutter/material.dart';

import '../core/constants/app_constants.dart';
import '../models/article_model.dart';
import '../repositories/article_repository.dart';

class PopularProvider extends ChangeNotifier {
  PopularProvider(this._articleRepository);

  final ArticleRepository _articleRepository;

  List<ArticleModel> _items = <ArticleModel>[];
  bool _isLoadingInitial = false;
  bool _isLoadingMore = false;
  bool _hasMore = true;
  String? _error;
  int _limit = AppConstants.popularInitialLimit;

  List<ArticleModel> get items => _items;
  bool get isLoadingInitial => _isLoadingInitial;
  bool get isLoadingMore => _isLoadingMore;
  bool get hasMore => _hasMore;
  String? get error => _error;

  Future<void> fetchInitial() async {
    _isLoadingInitial = true;
    _error = null;
    _limit = AppConstants.popularInitialLimit;
    _hasMore = true;
    notifyListeners();

    final result = await _articleRepository.fetchPopular(limit: _limit);
    if (result.isSuccess && result.data != null) {
      _items = result.data!;
    } else {
      _error = result.error;
    }

    _isLoadingInitial = false;
    notifyListeners();
  }

  Future<void> fetchMore() async {
    if (_isLoadingMore || !_hasMore) return;

    _isLoadingMore = true;
    _error = null;
    notifyListeners();

    _limit += AppConstants.popularLimitStep;
    final result = await _articleRepository.fetchPopular(limit: _limit);
    if (result.isSuccess && result.data != null) {
      final previousCount = _items.length;
      final existingById = {for (final item in _items) item.id: item};
      for (final item in result.data!) {
        existingById[item.id] = item;
      }
      _items = existingById.values.toList(growable: false);
      if (_items.length <= previousCount) {
        _hasMore = false;
      }
    } else {
      _error = result.error;
    }

    _isLoadingMore = false;
    notifyListeners();
  }
}
