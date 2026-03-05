import 'package:flutter/material.dart';
import 'package:flutter_screenutil/flutter_screenutil.dart';
import 'package:loadmore/loadmore.dart';

import '../../app_scope.dart';
import '../../models/article_model.dart';
import '../../models/category_model.dart';
import '../../widgets/app_scaffold/app_drawer.dart';
import '../../widgets/app_scaffold/app_top_bar.dart';
import '../../widgets/article/popular_article_carousel.dart';
import '../../widgets/category/category_grid.dart';
import '../../widgets/common/app_refresh_indicator.dart';
import '../../widgets/common/empty_state.dart';
import '../../widgets/common/error_state.dart';
import '../../widgets/common/load_more_trigger.dart';
import '../../widgets/common/loading_indicator.dart';
import '../article_detail/article_detail_screen.dart';
import '../auth/login_screen.dart';
import '../category/category_screen.dart';
import '../profile/profile_screen.dart';
import '../search/search_screen.dart';
import '../settings/settings_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final scope = AppScope.of(context);
      scope.homeCategoriesProvider.fetchInitial();
      scope.popularProvider.fetchInitial();
    });
  }

  @override
  Widget build(BuildContext context) {
    final scope = AppScope.of(context);
    final auth = scope.authProvider;
    final profile = scope.profileProvider.profile;

    return Scaffold(
      appBar: AppTopBar(
        title: 'News',
        onSearch: () => Navigator.of(
          context,
        ).push(MaterialPageRoute(builder: (_) => const SearchScreen())),
        onSettings: () => Navigator.of(
          context,
        ).push(MaterialPageRoute(builder: (_) => const SettingsScreen())),
      ),
      drawer: AppDrawer(
        userName: profile.name,
        email: auth.email,
        photoPath: profile.photoPath,
        onProfile: () {
          Navigator.of(context).pop();
          Navigator.of(
            context,
          ).push(MaterialPageRoute(builder: (_) => const ProfileScreen()));
        },
        onSettings: () {
          Navigator.of(context).pop();
          Navigator.of(
            context,
          ).push(MaterialPageRoute(builder: (_) => const SettingsScreen()));
        },
        onLogout: () {
          auth.logout();
          Navigator.of(context).pushAndRemoveUntil(
            MaterialPageRoute(builder: (_) => const LoginScreen()),
            (_) => false,
          );
        },
      ),
      body: AppRefreshIndicator(
        onRefresh: () async {
          await Future.wait([
            scope.homeCategoriesProvider.fetchInitial(),
            scope.popularProvider.fetchInitial(),
          ]);
        },
        child: AnimatedBuilder(
          animation: scope.popularProvider,
          builder: (context, _) => LoadMore(
            isFinish: !scope.popularProvider.hasMore,
            onLoadMore: () async {
              if (scope.popularProvider.isLoadingMore ||
                  !scope.popularProvider.hasMore) {
                return false;
              }
              await scope.popularProvider.fetchMore();
              return scope.popularProvider.hasMore;
            },
            child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: EdgeInsets.all(16.w),
              children: [
                Text('Categories', style: Theme.of(context).textTheme.titleLarge),
                SizedBox(height: 12.h),
                _CategorySection(
                  onTapCategory: (category) {
                    Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => CategoryScreen(category: category),
                      ),
                    );
                  },
                ),
                SizedBox(height: 24.h),
                Text('Popular', style: Theme.of(context).textTheme.titleLarge),
                SizedBox(height: 12.h),
                _PopularSection(
                  onTapArticle: (article) {
                    Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) =>
                            ArticleDetailScreen(articleId: article.id),
                      ),
                    );
                  },
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _CategorySection extends StatelessWidget {
  const _CategorySection({required this.onTapCategory});

  final void Function(CategoryModel category) onTapCategory;

  @override
  Widget build(BuildContext context) {
    final provider = AppScope.of(context).homeCategoriesProvider;
    return AnimatedBuilder(
      animation: provider,
      builder: (context, _) {
        if (provider.isLoading) return const LoadingIndicator();
        if (provider.error != null) {
          return ErrorState(
            message: provider.error!,
            onRetry: provider.fetchInitial,
          );
        }
        if (provider.visibleCategories.isEmpty) {
          return const EmptyState(message: 'No categories available.');
        }

        return Column(
          children: [
            CategoryGrid(
              items: provider.visibleCategories,
              onTapCategory: onTapCategory,
            ),
            if (provider.canLoadMoreWhenUnfiltered)
              LoadMoreTrigger(
                onPressed: provider.loadMore,
                isLoading: false,
                label: 'Show more categories',
              ),
          ],
        );
      },
    );
  }
}

class _PopularSection extends StatelessWidget {
  const _PopularSection({required this.onTapArticle});

  final void Function(ArticleModel article) onTapArticle;

  @override
  Widget build(BuildContext context) {
    final provider = AppScope.of(context).popularProvider;
    return AnimatedBuilder(
      animation: provider,
      builder: (context, _) {
        if (provider.isLoadingInitial) return const LoadingIndicator();
        if (provider.error != null && provider.items.isEmpty) {
          return ErrorState(
            message: provider.error!,
            onRetry: provider.fetchInitial,
          );
        }
        if (provider.items.isEmpty) {
          return const EmptyState(message: 'No popular articles yet.');
        }

        return Column(
          children: [
            PopularArticleList(
              items: provider.items,
              onTapArticle: onTapArticle,
            ),
          ],
        );
      },
    );
  }
}
