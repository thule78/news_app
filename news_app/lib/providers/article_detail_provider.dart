import 'package:flutter/material.dart';

import '../models/article_detail_model.dart';
import '../repositories/article_repository.dart';

class ArticleDetailProvider extends ChangeNotifier {
  ArticleDetailProvider(this._articleRepository);

  final ArticleRepository _articleRepository;

  final Map<int, ArticleDetailModel> _details = <int, ArticleDetailModel>{};
  final Set<int> _bookmarkedIds = <int>{};
  final Set<int> _likedIds = <int>{};
  bool _isLoading = false;
  String? _error;

  bool get isLoading => _isLoading;
  String? get error => _error;

  ArticleDetailModel? detailFor(int articleId) => _details[articleId];
  bool isBookmarked(int articleId) => _bookmarkedIds.contains(articleId);
  bool isLiked(int articleId) => _likedIds.contains(articleId);

  Future<void> fetchDetail(int articleId) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    final result = await _articleRepository.fetchDetail(articleId);
    if (result.isSuccess && result.data != null) {
      _details[articleId] = result.data!;
    } else {
      _error = result.error;
    }

    _isLoading = false;
    notifyListeners();
  }

  void toggleBookmark(int articleId) {
    if (_bookmarkedIds.contains(articleId)) {
      _bookmarkedIds.remove(articleId);
    } else {
      _bookmarkedIds.add(articleId);
    }
    notifyListeners();
  }

  void toggleLike(int articleId) {
    if (_likedIds.contains(articleId)) {
      _likedIds.remove(articleId);
    } else {
      _likedIds.add(articleId);
    }
    notifyListeners();
  }
}
