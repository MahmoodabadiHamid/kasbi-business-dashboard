"""Check running totals and the profit/loss gap between the two lines."""
import unittest

import pandas as pd

from finance.charts import ML_PRICING_START, cumulative_economic_trend, daily_economic_trend, format_money_chart, passenger_fare_share_daily_totals
import plotly.graph_objects as go


class CumulativeTrend(unittest.TestCase):
    def test_chronological_totals_stay_flat_on_no_trip_days(self):
        daily = pd.DataFrame([
            dict(date="2026-01-04", passenger_fare=100, driver_payout=120, contribution=-20),
            dict(date="2026-01-01", passenger_fare=100, driver_payout=110, contribution=-10),
            dict(date="2026-01-03", passenger_fare=100, driver_payout=80, contribution=20),
        ])
        fig = cumulative_economic_trend(daily)
        passenger_fare, cost = fig.data[-2:]
        self.assertEqual([trace.name for trace in fig.data if trace.showlegend is not False],["Daily passenger fare","Passenger fare","Driver payout"])
        self.assertEqual(list(passenger_fare.y), [10,10,20,30])
        self.assertEqual(list(cost.y), [11,11,19,31])
        self.assertEqual(fig.layout.yaxis.title.text,"Cumulative · Toman")
        self.assertIn("Toman",passenger_fare.hovertext[0])
        self.assertIn("1404.10.11",passenger_fare.hovertext[0])
        self.assertEqual(list(fig.layout.xaxis.ticktext),["1404.10.11","1404.10.12","1404.10.13","1404.10.14"])
        self.assertEqual(list(passenger_fare.x), list(pd.date_range("2026-01-01","2026-01-04")))
        self.assertEqual(passenger_fare.y[-1] - cost.y[-1], daily.contribution.sum()/10)
        bands = [trace for trace in fig.data if getattr(trace, "fill", None) == "toself"]
        self.assertEqual([band.name for band in bands],["Loss","Profit","Loss"])
        for band in bands:
            midpoint = len(band.y) // 2
            for revenue_value, cost_value in zip(band.y[:midpoint],band.y[midpoint:][::-1]):
                gap = revenue_value - cost_value
                self.assertGreaterEqual(gap,0) if band.name == "Profit" else self.assertLessEqual(gap,0)
            for crossing, value in ((pd.Timestamp("2026-01-02 12:00"),15), (pd.Timestamp("2026-01-03 12:00"),25)):
                if crossing in band.x:
                    self.assertEqual([y for x,y in zip(band.x,band.y) if x == crossing],[value,value])
        self.assertEqual(list(next(trace for trace in fig.data if trace.name == "Base area").y),[10,10,19,30])
        bars = next(trace for trace in fig.data if trace.type == "bar")
        self.assertEqual(list(bars.y), [10, 10, 10])
        self.assertEqual(list(bars.x), list(pd.to_datetime(["2026-01-01", "2026-01-03", "2026-01-04"])))
        self.assertEqual(sum(bars.y), passenger_fare.y[-1])
        self.assertEqual(bars.yaxis, "y2")
        self.assertIn("1404.10.11", bars.hovertext[0])
        self.assertIn("Toman", bars.hovertext[0])

    def test_single_day_and_zero_contribution(self):
        for contribution in (-10,0,10):
            with self.subTest(contribution=contribution):
                fig = cumulative_economic_trend(pd.DataFrame([
                    dict(date="2026-01-01",passenger_fare=100,driver_payout=100-contribution,contribution=contribution),
                ]))
                passenger_fare, cost = fig.data[-2:]
                self.assertEqual(passenger_fare.y[0] - cost.y[0],contribution/10)
                self.assertEqual([trace.name for trace in fig.data],["Daily passenger fare","Base area","Passenger fare","Driver payout"])

    def test_break_even_period_does_not_join_profit_and_loss_areas(self):
        daily = pd.DataFrame([
            dict(date="2026-01-01",passenger_fare=100,driver_payout=90),
            dict(date="2026-01-02",passenger_fare=100,driver_payout=110),
            dict(date="2026-01-03",passenger_fare=100,driver_payout=100),
            dict(date="2026-01-04",passenger_fare=100,driver_payout=110),
        ])
        fig = cumulative_economic_trend(daily)
        profit, loss = [trace for trace in fig.data if getattr(trace, "fill", None) == "toself"]
        self.assertEqual(max(profit.x),pd.Timestamp("2026-01-02"))
        self.assertEqual(min(loss.x),pd.Timestamp("2026-01-03"))

    def test_empty_daily_totals(self):
        fig = cumulative_economic_trend(pd.DataFrame(columns=["date","passenger_fare","driver_payout","contribution"]))
        self.assertTrue(all(len(trace.y) == 0 for trace in fig.data))

    def test_compact_money_axes_and_hover_preserve_geometry(self):
        fig = go.Figure()
        fig.add_bar(x=["A", "B"], y=[4_000_000_000, -6_000_000], name="Contribution")
        fig.update_yaxes(title="Toman")
        format_money_chart(fig)
        self.assertEqual(list(fig.data[0].y), [4_000_000_000, -6_000_000])
        self.assertEqual(list(fig.data[0].hovertext), ["A<br>4 B Toman", "B<br>-6 M Toman"])
        self.assertTrue(any(" B" in label for label in fig.layout.yaxis.ticktext))

        horizontal = go.Figure(go.Bar(x=[6_000_000], y=["Customer"], orientation="h"))
        horizontal.update_xaxes(title="Toman")
        format_money_chart(horizontal)
        self.assertEqual(horizontal.data[0].hovertext[0], "6 M Toman<br>Customer")
        self.assertTrue(any(" M" in label for label in horizontal.layout.xaxis.ticktext))

    def test_daily_bars_and_ml_hover_use_independent_axes(self):
        daily = pd.DataFrame([
            dict(date="2026-10-16", passenger_fare=40_000_000_000, driver_payout=30_000_000_000),
            dict(date="2026-10-17", passenger_fare=20_000_000_000, driver_payout=15_000_000_000),
            dict(date="2026-10-17", passenger_fare=10_000_000_000, driver_payout=5_000_000_000),
        ])
        original = daily.copy(deep=True)
        fig = cumulative_economic_trend(daily)
        bars = next(trace for trace in fig.data if trace.type == "bar")
        passenger_fare = next(trace for trace in fig.data if trace.name == "Passenger fare")
        marker = next(trace for trace in fig.data if trace.name == "ML pricing")
        self.assertEqual(list(bars.y), [4_000_000_000, 3_000_000_000])
        self.assertEqual(passenger_fare.y[-1], 7_000_000_000)
        self.assertEqual(list(fig.layout.yaxis2.range), [0, 16_000_000_000])
        self.assertEqual(fig.layout.yaxis2.title.text, "Daily passenger fare · Toman")
        self.assertEqual(marker.yaxis, "y3")
        self.assertFalse(fig.layout.yaxis3.visible)
        format_money_chart(fig)
        self.assertEqual(bars.hovertext[1], "1405.07.25<br>3 B Toman")
        self.assertIn("ML pricing", marker.hovertemplate)
        self.assertTrue(any(" B" in label for label in fig.layout.yaxis2.ticktext))
        pd.testing.assert_frame_equal(daily, original)


class DailyTrend(unittest.TestCase):
    def test_average_profit_is_weighted_and_updates_with_selected_days(self):
        daily = pd.DataFrame([
            dict(date="2026-01-01", passenger_fare=100, driver_payout=50),
            dict(date="2026-01-03", passenger_fare=900, driver_payout=810),
        ])
        fig = daily_economic_trend(daily)
        average = next(trace for trace in fig.data if trace.name == "Average profit")
        self.assertAlmostEqual(average.y[0], .86)
        self.assertAlmostEqual(average.y[-1], .86)
        self.assertEqual(average.line.dash, "dash")
        self.assertEqual(average.line.color, "#586574")
        self.assertIn("Average profit: 14.0%", average.hovertemplate)
        self.assertFalse(fig.layout.annotations)
        selected = daily_economic_trend(daily.iloc[:1])
        selected_average = next(trace for trace in selected.data if trace.name == "Average profit")
        self.assertAlmostEqual(selected_average.y[0], .5)
        self.assertIn("Average profit: 50.0%", selected_average.hovertemplate)

    def test_negative_average_uses_loss_band_height_and_hover_only(self):
        fig = daily_economic_trend(pd.DataFrame([
            dict(date="2026-01-01", passenger_fare=100, driver_payout=125),
        ]))
        average = next(trace for trace in fig.data if trace.name == "Average profit")
        self.assertEqual(average.y[0], .75)
        self.assertIn("Average profit: -25.0%", average.hovertemplate)
        self.assertFalse(fig.layout.annotations)
        self.assertEqual(list(fig.layout.yaxis.range), [.7, 1])
        empty = daily_economic_trend(pd.DataFrame(columns=["date", "passenger_fare", "driver_payout"]))
        self.assertFalse(any(trace.name == "Average profit" for trace in empty.data))
        self.assertFalse(empty.layout.annotations)

    def test_no_hardcoded_dates_are_removed_from_baseline_chart(self):
        daily = pd.DataFrame([
            dict(date="2026-07-03", passenger_fare=100, driver_payout=50),
            dict(date="2026-07-31", passenger_fare=100, driver_payout=150),
        ])
        original = daily.copy(deep=True)
        included = passenger_fare_share_daily_totals(daily)
        self.assertEqual(len(included),2)
        self.assertEqual(int((included.driver_payout > included.passenger_fare).sum()),1)
        fig = daily_economic_trend(daily)
        self.assertEqual(len(fig.data[-1].customdata),2)
        pd.testing.assert_frame_equal(daily,original)

    def test_daily_totals_remove_missing_days_and_preserve_actual_losses(self):
        daily = pd.DataFrame([
            dict(date="2026-01-04", passenger_fare=100, driver_payout=130),
            dict(date="2026-01-01", passenger_fare=100, driver_payout=50),
            dict(date="2026-01-01", passenger_fare=300, driver_payout=270),
            dict(date="2026-01-03", passenger_fare=200, driver_payout=200),
        ])
        original = daily.copy(deep=True)
        fig = daily_economic_trend(daily)
        boundary = fig.data[-1]
        self.assertEqual(list(boundary.x), [0, 1, 2])
        self.assertAlmostEqual(boundary.y[0], .8)
        self.assertAlmostEqual(boundary.y[1], 1)
        self.assertAlmostEqual(boundary.y[2], .7)
        self.assertEqual(list(fig.layout.xaxis.ticktext), ["1404.10.11", "1404.10.13", "1404.10.14"])
        self.assertEqual(fig.layout.xaxis.type, "linear")
        self.assertEqual(fig.layout.yaxis.range[0], .65)
        self.assertEqual(fig.layout.yaxis.range[1], 1)
        self.assertIn(1, fig.layout.yaxis.tickvals)
        self.assertEqual(fig.layout.yaxis.tickformat, ".0%")
        for row, expected_cost in zip(boundary.customdata, (.8, 1, 1.3)):
            self.assertAlmostEqual(row[1], expected_cost)
            self.assertAlmostEqual(row[2], 1 - expected_cost)
        loss_area = next(trace for trace in fig.data if trace.name == "Loss (overlay)")
        self.assertEqual(loss_area.fill, "toself")
        self.assertEqual(boundary.marker.opacity, 0)
        self.assertFalse(fig.layout.annotations)
        self.assertIn("Contribution margin", boundary.hovertemplate)
        self.assertIn("Loss day", boundary.customdata[-1][3])
        self.assertEqual(boundary.customdata[-1][4], "3 Toman")
        pd.testing.assert_frame_equal(daily, original)

    def test_equal_profit_and_loss_have_equal_colored_band_heights(self):
        fig = daily_economic_trend(pd.DataFrame([
            dict(date="2026-01-01", passenger_fare=100, driver_payout=70),
            dict(date="2026-01-03", passenger_fare=100, driver_payout=130),
        ]))
        costs, profit, loss_area, average, boundary = fig.data
        self.assertEqual(loss_area.mode, "lines")
        self.assertEqual(loss_area.fill, "toself")
        self.assertEqual(loss_area.fillcolor, "rgba(255,23,68,0.58)")
        self.assertAlmostEqual(costs.x[2], .5)
        self.assertEqual(costs.y[2], 1)
        self.assertAlmostEqual(profit.y[1] - costs.y[1], .3)
        self.assertAlmostEqual(1 - loss_area.y[3], .3)
        self.assertEqual(loss_area.y[2], 1)
        self.assertTrue(all(0 <= value <= 1 for trace in fig.data for value in trace.y))
        self.assertEqual(boundary.marker.opacity, 0)
        self.assertFalse(fig.layout.annotations)
        self.assertAlmostEqual(boundary.customdata[1][1], 1.3)
        self.assertAlmostEqual(boundary.customdata[1][2], -.3)

    def test_cost_and_profit_fills_partition_total_revenue(self):
        fig = daily_economic_trend(pd.DataFrame([
            dict(date="2026-01-01", passenger_fare=100, driver_payout=80),
            dict(date="2026-01-03", passenger_fare=100, driver_payout=40),
        ]))
        costs, profit, average, boundary = fig.data
        self.assertEqual(costs.fill, "tozeroy")
        self.assertEqual(costs.fillcolor, "rgba(255,59,141,0.28)")
        self.assertEqual(profit.fill, "tonexty")
        self.assertEqual(profit.fillcolor, "rgba(0,230,160,0.42)")
        self.assertEqual(list(costs.y), [.8, .8, .4, .4])
        self.assertEqual(list(profit.y), [1, 1, 1, 1])
        self.assertAlmostEqual(boundary.y[0], .8)
        self.assertAlmostEqual(boundary.y[1], .4)
        self.assertEqual(boundary.marker.opacity, 0)
        self.assertEqual(costs.line.width, 2)
        self.assertEqual(average.line.dash, "dash")
        self.assertEqual(profit.y[2] - costs.y[2], .6)

    def test_dense_loss_days_have_no_visible_markers_or_value_labels(self):
        daily = pd.DataFrame({
            "date": pd.date_range("2026-01-01", periods=20),
            "passenger_fare": [100] * 20,
            "driver_payout": list(range(110, 130)),
        })
        fig = daily_economic_trend(daily)
        self.assertFalse(fig.layout.annotations)
        self.assertTrue(all(trace.mode == "lines" or trace.marker.opacity == 0 for trace in fig.data))
        self.assertEqual(list(fig.layout.yaxis.range), [.65, 1])
        self.assertEqual(len(fig.data[-1].customdata), 20)
        self.assertAlmostEqual(fig.data[-1].customdata[-1][1], 1.29)
        self.assertAlmostEqual(fig.data[-1].customdata[-1][5], .29)

    def test_loss_above_100_percent_is_visually_capped_but_hover_is_exact(self):
        fig = daily_economic_trend(pd.DataFrame([
            dict(date="2026-01-01", passenger_fare=100, driver_payout=130),
            dict(date="2026-01-03", passenger_fare=100, driver_payout=250),
        ]))
        loss_area = next(trace for trace in fig.data if trace.name == "Loss (overlay)")
        # A 150% loss fills the available 100%; the 100% crossing is inserted.
        self.assertTrue(any(abs(x - 7/12) < 1e-10 and y == 0 for x, y in zip(loss_area.x, loss_area.y)))
        self.assertEqual(min(loss_area.y), 0)
        self.assertEqual(fig.data[-1].customdata[-1][1], 2.5)
        self.assertEqual(fig.data[-1].customdata[-1][5], 1.5)
        self.assertEqual(list(fig.layout.yaxis.range), [0, 1])

    def test_zoom_preserves_percentage_values_and_all_boundaries(self):
        for driver_costs, expected_low in (([92, 96], .85), ([100, 100], .9), ([0, 95], 0), ([110, 120], .75)):
            with self.subTest(driver_costs=driver_costs):
                fig = daily_economic_trend(pd.DataFrame({
                    "date": pd.date_range("2026-01-01", periods=2),
                    "passenger_fare": [100, 100], "driver_payout": driver_costs,
                }))
                self.assertEqual(list(fig.layout.yaxis.range), [expected_low, 1])
                self.assertEqual(fig.layout.yaxis.tickvals[-1], 1)
                self.assertTrue(all(expected_low <= value <= 1 for value in fig.data[-1].y))
                self.assertEqual([row[1] for row in fig.data[-1].customdata], [value / 100 for value in driver_costs])


class PricingMarker(unittest.TestCase):
    def test_date_and_compressed_plots_mark_start_with_hover_only(self):
        for dates in (("2026-10-16", "2026-10-17", "2026-10-18"), ("2026-10-16", "2026-10-19"), ("2026-10-17",)):
            daily = pd.DataFrame(dict(date=dates, passenger_fare=[100] * len(dates), driver_payout=[90] * len(dates)))
            for build in (cumulative_economic_trend, daily_economic_trend):
                with self.subTest(dates=dates, build=build.__name__):
                    fig = build(daily)
                    marker = next(trace for trace in fig.data if trace.name == "ML pricing")
                    line = next(shape for shape in fig.layout.shapes if shape.type == "line" and shape.yref == "paper")
                    expected_x = ML_PRICING_START if build == cumulative_economic_trend else (-.5 if len(dates) == 1 else .5)
                    self.assertEqual(line.x0, expected_x)
                    self.assertEqual(line.x1, expected_x)
                    self.assertEqual((line.y0, line.y1), (0, 1))
                    self.assertEqual(set(marker.x), {expected_x})
                    self.assertEqual(marker.marker.opacity, 0)
                    self.assertFalse(marker.showlegend)
                    self.assertFalse(fig.layout.annotations)
                    self.assertIn("ML pricing", marker.hovertemplate)
                    self.assertIn("1405.07.25", marker.hovertemplate)
                    self.assertIn("17 October 2026", marker.hovertemplate)
                    previous_ticks = fig.layout.yaxis.ticktext
                    format_money_chart(fig)
                    self.assertIn("ML pricing", marker.hovertemplate)
                    self.assertEqual(fig.layout.yaxis.ticktext, previous_ticks)
                    if build == daily_economic_trend:
                        split = next(trace for trace in fig.data if trace.name == "Passenger fare split")
                        self.assertEqual(len(split.x), len(dates))
                        self.assertEqual(list(fig.layout.yaxis.range), [.85, 1])

    def test_outside_visible_dates_does_not_extend_plot(self):
        for dates in (("2026-10-01", "2026-10-16"), ("2026-10-18", "2026-10-20")):
            daily = pd.DataFrame(dict(date=dates, passenger_fare=[100, 100], driver_payout=[90, 90]))
            for build in (cumulative_economic_trend, daily_economic_trend):
                fig = build(daily)
                self.assertFalse(any(trace.name == "ML pricing" for trace in fig.data))

    def test_empty_single_day_and_zero_revenue(self):
        empty = daily_economic_trend(pd.DataFrame(columns=["date", "passenger_fare", "driver_payout"]))
        self.assertTrue(all(len(trace.y) == 0 for trace in empty.data))
        for passenger_fare in (0, 100):
            with self.subTest(passenger_fare=passenger_fare):
                fig = daily_economic_trend(pd.DataFrame([
                    dict(date="2026-01-01", passenger_fare=passenger_fare, driver_payout=125),
                ]))
                if passenger_fare == 0:
                    self.assertTrue(all(len(trace.y) == 0 for trace in fig.data))
                else:
                    self.assertEqual(list(fig.data[0].x), [-.5, 0, .5])
                    self.assertEqual(list(fig.data[0].y), [1, 1, 1])
                    self.assertEqual(list(fig.data[-1].customdata[0][:3]), ["1404.10.11", 1.25, -.25])
