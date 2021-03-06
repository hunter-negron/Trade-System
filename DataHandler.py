# DataHandler.py

import datetime
import os, os.path
import pandas as pd

from abc import ABCMeta, abstractmethod

from Event import MarketEvent

class DataHandler(object):
    """
    DataHandler is an abstract base class providing an interface for
    all subsequent (inherited) data handlers (both live and historic).

    The goal of a (derived) DataHandler object is to output a generated
    set of bars (OLHCVI) for each symbol requested.

    This will replicate how a live strategy would function as current
    market data would be sent "down the pipe". Thus a historic and live
    system will be treated identically by the rest of the backtesting suite.
    """

    __metaclass__ = ABCMeta

    @abstractmethod
    def get_latest_bars(self, symbol, N=1):
        """
        Returns the last N bars from the latest_symbol list,
        or fewer if less bars are available.
        """
        raise NotImplementedError("Should implement get_latest_bars()")

    @abstractmethod
    def update_bars(self):
        """
        Pushes the latest bar to the latest symbol structure
        for all symbols in the symbol list.
        """
        raise NotImplementedError("Should implement update_bars()")

class HistoricCSVDataHandler(DataHandler):
    """
    HistoricCSVDataHandler is designed to read CSV files for
    each requested symbol from disk and provide an interface
    to obtain the "latest" bar in a manner identical to a live
    trading interface.
    """

    def __init__(self, events, csv_dir, symbol_list):
        """
        Initialises the historic data handler by requesting
        the location of the CSV files and a list of symbols.

        It will be assumed that all files are of the form
        'symbol.csv', where symbol is a string in the list.

        Parameters:
        events - The Event Queue.
        csv_dir - Absolute directory path to the CSV files.
        symbol_list - A list of symbol strings.
        """
        self.events = events
        self.csv_dir = csv_dir
        self.symbol_list = symbol_list

        self.symbol_data = {}
        self.latest_symbol_data = {}
        self.continue_backtest = True

        #self._open_convert_csv_files()
        self._new_open_convert_csv_files()

        # Instiantiate the generators
        self.new_bar = {k:v for (k,v) in [(s, self._get_new_bar(s)) for s in symbol_list]}

    def _open_convert_csv_files(self):
        """
        Opens the CSV files from the data directory, converting
        them into pandas DataFrames within a symbol dictionary.

        For this handler it will be assumed that the data is
        taken from DTN IQFeed. Thus its format will be respected.
        """
        comb_index = None
        for s in self.symbol_list:
            # Load the CSV file with no header information, indexed on date
            self.symbol_data[s] = pd.io.parsers.read_csv(
                                      os.path.join(self.csv_dir, '%s.csv' % s),
                                      header=0, index_col=0,
                                      names=['datetime','open','low','high','close','volume','oi']
                                  )

            # Combine the index to pad forward values
            if comb_index is None:
                comb_index = self.symbol_data[s].index
            else:
                comb_index.union(self.symbol_data[s].index)

            # Set the latest symbol_data to None
            self.latest_symbol_data[s] = []

        # Reindex the dataframes
        for s in self.symbol_list:
            self.symbol_data[s] = self.symbol_data[s].reindex(index=comb_index, method='pad').iterrows()

    def _new_open_convert_csv_files(self):
        '''
        To handle CSVs that are in a different form than the tutorial.
        _get_new_bar() also considers this format, diverging from the tutorial.
        Date,Open,High,Low,Close,Adj Close,Volume
        '''
        comb_index = None
        for s in self.symbol_list:
            # Load the CSV files, which already have the Yahoo headers
            self.symbol_data[s] = pd.read_csv(os.path.join(self.csv_dir, '%s.csv' % s)).dropna().reset_index(drop = True)

            # Combine the index to pad forward values
            if comb_index is None:
                comb_index = self.symbol_data[s].index
            else:
                comb_index.union(self.symbol_data[s].index)

            # Set the latest symbol_data to None
            self.latest_symbol_data[s] = []

        # Reindex the dataframes
        for s in self.symbol_list:
            self.symbol_data[s] = self.symbol_data[s].reindex(index=comb_index, method='pad').iterrows()

    def _get_new_bar(self, symbol):
        """
        Returns the latest bar from the data feed as a tuple of
        (sybmbol, datetime, open, high, low, close, adj close, volume).
        """
        for b in self.symbol_data[symbol]:
            yield tuple([symbol, b[1][0], b[1][1], b[1][2], b[1][3], b[1][4], b[1][5], b[1][6]])

    def get_latest_bars(self, symbol, N=1):
        """
        Returns the last N bars from the latest_symbol list,
        or N-k if less available.
        """
        try:
            bars_list = self.latest_symbol_data[symbol]
        except KeyError:
            print("That symbol is not available in the historical data set.")
        else:
            return bars_list[-N:]

    def update_bars(self):
        """
        Pushes the latest bar to the latest_symbol_data structure
        for all symbols in the symbol list.
        """
        for s in self.symbol_list:
            try:
                bar = next(self.new_bar[s])
            except StopIteration:
                self.continue_backtest = False
            else:
                if bar is not None:
                    self.latest_symbol_data[s].append(bar)
        self.events.append(MarketEvent())

class SimpleCSVHandler(DataHandler):
    '''
    SimpleCSVHandler mimics the functionality of HistoricCSVDataHandler
    but works with only one CSV file, hence one symbol and period, at a
    time.
    '''

    def __init__(self, events, csv):
        '''
        eventQ - the queue onto which to push new events
        csv - absolute directory path string to the CSV file
        '''
        self.events = events
        self.csv = csv

        self.latest_symbol_data = []
        self.continue_backtest = True

        # open the CSV into a pandas dataframe, remove null rows
        self.bars = pd.read_csv(csv).dropna().reset_index(drop = True)

        # create the generator for the bars
        self.new_bar = self._get_new_bar()

    def _get_new_bar(self):
        for b in self.bars.iterrows():
            yield (b[1][0], b[1][1], b[1][2], b[1][3], b[1][4], b[1][5], b[1][6])

    def get_latest_bars(self, symbol=None, N=1):
        return self.latest_symbol_data[-N:]

    def update_bars(self):
        try:
            bar = next(self.new_bar)
        except StopIteration:
            self.continue_backtest = False
        else:
            if bar is not None:
                self.latest_symbol_data.append(bar)
        self.events.append(MarketEvent())
